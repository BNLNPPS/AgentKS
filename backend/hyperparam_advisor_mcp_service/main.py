#!/usr/bin/env python3
"""
Hyperparameter Advisor MCP Server

Exposes hyperparameter optimization tools via MCP protocol:
- hyperparam_inject: Inject optimization results into RAG
- hyperparam_suggest: Get suggestions based on historical data
"""

import asyncio
import json
import logging
import os
import sys
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hyperparam_advisor_mcp")

# Environment configuration
RAG_INJECTOR_URL = os.getenv("RAG_INJECTOR_URL", "http://localhost:4002")
RAG_GROUP_NAME = os.getenv("HYPERPARAM_RAG_GROUP", "hyperparameter-optimization")
RAG_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
USE_LLM_ANALYSIS = os.getenv("USE_LLM_ANALYSIS", "true").lower() == "true"
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:4000/v1/chat/completions")

# Initialize MCP server
server = Server("hyperparam-advisor")


def format_hyperparam_doc(
    hyperparameters: Dict[str, Any],
    result: float,
    experiment_id: str,
    result_type: str = "maximize",
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Format hyperparameter result as a document for RAG ingestion"""
    timestamp = datetime.now().isoformat()
    
    doc = f"""Experiment: {experiment_id}
Timestamp: {timestamp}
Result Type: {result_type}
Result Value: {result}

Hyperparameters:
"""
    for key, value in hyperparameters.items():
        doc += f"  - {key}: {value}\n"
    
    if metadata:
        doc += "\nMetadata:\n"
        for key, value in metadata.items():
            doc += f"  - {key}: {value}\n"
    
    return doc


def parse_rag_results(rag_docs: List[Any]) -> List[Dict[str, Any]]:
    """Parse RAG documents back into hyperparameter result objects"""
    results = []
    
    for doc in rag_docs:
        try:
            content = doc.get("page_content", "") if isinstance(doc, dict) else str(doc)
            
            lines = content.split('\n')
            hyperparams = {}
            result_value = 0.0
            result_type = "maximize"
            experiment_id = ""
            
            in_hyperparams = False
            for line in lines:
                if line.startswith("Experiment:"):
                    experiment_id = line.split(":", 1)[-1].strip()
                elif line.startswith("Result Value:"):
                    result_value = float(line.split(":")[-1].strip())
                elif line.startswith("Result Type:"):
                    result_type = line.split(":")[-1].strip()
                elif line.startswith("Hyperparameters:"):
                    in_hyperparams = True
                elif in_hyperparams and line.strip().startswith("- "):
                    parts = line.strip()[2:].split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # Try to parse as number
                        try:
                            if '.' in value:
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            pass
                        hyperparams[key] = value
                elif line.startswith("Metadata:"):
                    in_hyperparams = False
            
            if hyperparams:
                results.append({
                    "experiment_id": experiment_id,
                    "hyperparameters": hyperparams,
                    "result": result_value,
                    "result_type": result_type
                })
        except Exception as e:
            logger.warning(f"Failed to parse document: {e}")
            continue
    
    return results


async def inject_to_rag(documents: List[str], scope: str = "private", user_id: str = "anonymous") -> Dict[str, Any]:
    """Inject documents into RAG system via HTTP POST to rag injector"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Ensure RAG group exists
            try:
                response = await client.get(
                    f"{RAG_INJECTOR_URL}/groups/{RAG_GROUP_NAME}",
                    params={"scope": scope}
                )
                if response.status_code == 404:
                    # Create the group
                    logger.info(f"Creating RAG group: {RAG_GROUP_NAME}")
                    create_response = await client.post(
                        f"{RAG_INJECTOR_URL}/groups",
                        json={
                            "name": RAG_GROUP_NAME,
                            "scope": scope,
                            "owner": user_id,
                            "description": "Hyperparameter optimization results for ML experiments",
                            "embed_model": RAG_EMBED_MODEL
                        }
                    )
                    create_response.raise_for_status()
                    logger.info(f"Created RAG group: {RAG_GROUP_NAME}")
                elif response.status_code == 200:
                    logger.info(f"RAG group {RAG_GROUP_NAME} already exists")
                else:
                    response.raise_for_status()
            except Exception as e:
                logger.error(f"Error checking/creating RAG group: {e}")
                raise
            
            # 2. Inject documents
            injected_count = 0
            errors = []
            
            for i, doc_content in enumerate(documents):
                try:
                    # Generate unique title based on content hash
                    doc_hash = doc_content[:100]  # Use first 100 chars as identifier
                    title = f"hyperparam_result_{i}_{hash(doc_content) % 10000}"
                    
                    inject_response = await client.post(
                        f"{RAG_INJECTOR_URL}/inject/{RAG_GROUP_NAME}",
                        params={"scope": scope},
                        json={
                            "title": title,
                            "content": doc_content,
                            "metadata": {
                                "type": "hyperparameter_optimization",
                                "user_id": user_id,
                                "injected_at": datetime.now().isoformat()
                            },
                            "chunk_size": 1000,
                            "chunk_overlap": 200
                        }
                    )
                    
                    if inject_response.status_code == 200:
                        injected_count += 1
                        logger.info(f"Injected document {i+1}/{len(documents)}: {title}")
                    elif inject_response.status_code == 409:
                        # Duplicate - not an error
                        logger.info(f"Document {i+1} already exists (duplicate)")
                        injected_count += 1
                    else:
                        error_msg = f"Failed to inject document {i+1}: {inject_response.status_code}"
                        logger.warning(error_msg)
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Error injecting document {i+1}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            return {
                "success": True,
                "count": injected_count,
                "total": len(documents),
                "message": f"Injected {injected_count}/{len(documents)} documents to RAG",
                "errors": errors if errors else None
            }
            
    except Exception as e:
        logger.error(f"RAG injection failed: {e}", exc_info=True)
        return {
            "success": False,
            "count": 0,
            "message": f"RAG injection failed: {str(e)}"
        }


async def query_rag(query: str, k: int = 10, user_id: str = "anonymous") -> List[Dict[str, Any]]:
    """Query RAG system for relevant documents"""
    try:
        # Import RAG common utilities
        from rag_common import get_vector_store_for_model, LANGCHAIN_AVAILABLE
        
        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain not available, cannot query RAG")
            return []
        
        # Get vector store for the hyperparameter RAG group
        vector_store = get_vector_store_for_model(RAG_EMBED_MODEL)
        if not vector_store:
            logger.warning(f"Failed to get vector store for model: {RAG_EMBED_MODEL}")
            return []
        
        # Perform similarity search with filter for our RAG group
        logger.info(f"Querying RAG: {query} (k={k})")
        
        search_kwargs = {
            "k": k,
            "filter": {"rag_group": RAG_GROUP_NAME}
        }
        
        results = vector_store.similarity_search_with_score(query, **search_kwargs)
        
        # Convert to list of dicts
        documents = []
        for doc, score in results:
            documents.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata,
                "similarity_score": float(score)
            })
        
        logger.info(f"Retrieved {len(documents)} documents from RAG")
        return documents
        
    except Exception as e:
        logger.error(f"RAG query error: {e}", exc_info=True)
        return []


async def llm_analyze_and_suggest(
    historical_results: List[Dict[str, Any]],
    target_params: List[str],
    result_type: str,
    n_suggestions: int,
    constraints: Optional[Dict[str, Any]] = None,
    current_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Use LLM to analyze historical data and generate intelligent suggestions"""
    
    try:
        # Sort results by performance
        sorted_results = sorted(
            historical_results,
            key=lambda x: x["result"],
            reverse=(result_type == "maximize")
        )
        
        # Prepare context for LLM
        prompt = f"""You are an expert in hyperparameter optimization for machine learning. Analyze the following historical optimization results and suggest {n_suggestions} promising hyperparameter configurations.

**Optimization Goal**: {result_type.upper()} the result metric

**Historical Results** (sorted by performance, best first):
"""
        
        # Include top 10 historical results
        for i, res in enumerate(sorted_results[:10], 1):
            prompt += f"\n{i}. Result: {res['result']:.4f}"
            if "experiment_id" in res:
                prompt += f" (Experiment: {res['experiment_id']})"
            prompt += "\n   Hyperparameters:\n"
            for key, val in res["hyperparameters"].items():
                prompt += f"     - {key}: {val}\n"
        
        prompt += f"\n**Target Hyperparameters**: {', '.join(target_params)}\n"
        
        if current_params:
            prompt += f"\n**Current Configuration** (for reference):\n"
            for key, val in current_params.items():
                prompt += f"  - {key}: {val}\n"
        
        if constraints:
            prompt += f"\n**Constraints**:\n"
            for param, constraint in constraints.items():
                if "choices" in constraint:
                    # Categorical parameter
                    choices_str = ", ".join([f"'{c}'" for c in constraint["choices"]])
                    prompt += f"  - {param} (categorical): must be one of [{choices_str}]\n"
                else:
                    # Numeric parameter
                    prompt += f"  - {param}:"
                    if "min" in constraint:
                        prompt += f" min={constraint['min']}"
                    if "max" in constraint:
                        prompt += f" max={constraint['max']}"
                    if "default" in constraint:
                        prompt += f" default={constraint['default']}"
                    prompt += "\n"
        
        prompt += f"""
**Task**: Based on the patterns in the historical data, suggest {n_suggestions} diverse hyperparameter configurations that are likely to perform well. Consider:

1. **Trends**: What patterns do you see in successful configurations?
2. **Exploration vs Exploitation**: Balance between staying near known good configs and exploring new areas
3. **Parameter Interactions**: Consider how hyperparameters might interact
4. **Constraints**: Respect any specified bounds
   - For numeric parameters: stay within min/max bounds
   - For categorical parameters: only use values from the specified choices
5. **New Parameters**: For parameters not in historical data, suggest reasonable starting values based on ML best practices
6. **Diversity**: Ensure suggestions explore different regions of the hyperparameter space
7. **Categorical Parameters**: If a parameter has categorical constraints (choices), select from those values based on patterns or best practices

**Output Format** (JSON only, no markdown):
{{
  "suggestions": [
    {{"learning_rate": 0.001, "batch_size": 32, "optimizer": "adam", ...}},
    {{"learning_rate": 0.005, "batch_size": 64, "optimizer": "sgd", ...}},
    ...
  ],
  "rationale": "Detailed explanation of why these suggestions were made, what patterns were observed, and the strategy behind each suggestion.",
  "confidence": 0.85,
  "insights": [
    "Key insight 1 about the data",
    "Key insight 2 about parameter relationships",
    "Key insight 3 about categorical parameter performance",
    ...
  ]
}}

Respond with ONLY the JSON object, no other text."""
        
        # Call LLM API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                LLM_API_URL,
                json={
                    "model": "rag-agent",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert ML hyperparameter optimization advisor. Provide detailed, actionable suggestions based on historical data."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                return None
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Parse JSON from response
            # Try to extract JSON if wrapped in markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            llm_result = json.loads(content)
            
            # Validate and post-process suggestions
            validated_suggestions = []
            for suggestion in llm_result.get("suggestions", []):
                # Apply constraints if LLM didn't
                if constraints:
                    for param, constraint in constraints.items():
                        if param in suggestion:
                            if "choices" in constraint:
                                # Categorical parameter - ensure value is in allowed choices
                                choices = constraint["choices"]
                                if suggestion[param] not in choices:
                                    # Try case-insensitive match for strings
                                    if isinstance(suggestion[param], str):
                                        lower_choices = {str(c).lower(): c for c in choices}
                                        matched = lower_choices.get(suggestion[param].lower())
                                        if matched:
                                            suggestion[param] = matched
                                        else:
                                            # Invalid choice, use first valid choice
                                            logger.warning(f"LLM suggested invalid choice '{suggestion[param]}' for {param}, using {choices[0]}")
                                            suggestion[param] = choices[0]
                                    else:
                                        suggestion[param] = choices[0]
                            else:
                                # Numeric parameter - apply min/max bounds
                                if "min" in constraint:
                                    suggestion[param] = max(suggestion[param], constraint["min"])
                                if "max" in constraint:
                                    suggestion[param] = min(suggestion[param], constraint["max"])
                validated_suggestions.append(suggestion)
            
            llm_result["suggestions"] = validated_suggestions[:n_suggestions]
            return llm_result
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        logger.error(f"Response content: {content[:500]}")
        return None
    except Exception as e:
        logger.error(f"LLM analysis error: {e}", exc_info=True)
        return None


def generate_suggestions(
    historical_results: List[Dict[str, Any]],
    target_params: List[str],
    result_type: str,
    n_suggestions: int,
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate hyperparameter suggestions based on historical data using heuristics (fallback)"""
    
    if not historical_results:
        return {
            "suggestions": [],
            "rationale": "No historical results available. Please inject optimization results first.",
            "confidence": 0.0
        }
    
    # Sort results by performance
    sorted_results = sorted(
        historical_results,
        key=lambda x: x["result"],
        reverse=(result_type == "maximize")
    )
    
    # Find best configuration
    best_config = sorted_results[0]["hyperparameters"] if sorted_results else {}
    
    # Analyze categorical parameter frequencies
    categorical_frequencies = {}
    if constraints:
        for param, constraint in constraints.items():
            if "choices" in constraint:
                # Count frequency of each choice in historical results
                categorical_frequencies[param] = {}
                for result in sorted_results[:10]:  # Top 10 results
                    value = result["hyperparameters"].get(param)
                    if value is not None:
                        categorical_frequencies[param][value] = \
                            categorical_frequencies[param].get(value, 0) + 1
    
    # Generate suggestions based on best performing configs
    suggestions = []
    
    for i in range(min(n_suggestions, len(sorted_results))):
        suggestion = {}
        base_config = sorted_results[i]["hyperparameters"]
        
        for param in target_params:
            # Check if parameter has categorical constraints
            if constraints and param in constraints and "choices" in constraints[param]:
                # Handle categorical parameter
                choices = constraints[param]["choices"]
                
                # If we have frequency data, use weighted selection
                if param in categorical_frequencies and categorical_frequencies[param]:
                    # Sort choices by frequency (most frequent first)
                    sorted_choices = sorted(
                        categorical_frequencies[param].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                    # Use top choices with some exploration
                    if i < len(sorted_choices):
                        suggestion[param] = sorted_choices[i][0]
                    else:
                        # Explore less common choices
                        suggestion[param] = choices[i % len(choices)]
                elif param in base_config:
                    # Use value from base config if it's in allowed choices
                    value = base_config[param]
                    if value in choices:
                        suggestion[param] = value
                    else:
                        suggestion[param] = choices[i % len(choices)]
                else:
                    # Rotate through choices for diversity
                    suggestion[param] = choices[i % len(choices)]
                    
            elif param in base_config:
                value = base_config[param]
                # Apply small variations for numeric parameters
                if isinstance(value, (int, float)):
                    variation = 1.0 + (i * 0.1) * (1 if i % 2 == 0 else -1)
                    suggestion[param] = value * variation
                    
                    # Apply numeric constraints if provided
                    if constraints and param in constraints:
                        c = constraints[param]
                        if "min" in c:
                            suggestion[param] = max(suggestion[param], c["min"])
                        if "max" in c:
                            suggestion[param] = min(suggestion[param], c["max"])
                else:
                    # Keep string/other values as-is
                    suggestion[param] = value
            else:
                # Parameter not in historical data
                # Check if there's a default in constraints
                if constraints and param in constraints:
                    if "choices" in constraints[param]:
                        # Use first choice as default for categorical
                        suggestion[param] = constraints[param]["choices"][0]
                    elif "default" in constraints[param]:
                        suggestion[param] = constraints[param]["default"]
                    else:
                        suggestion[param] = None
                else:
                    suggestion[param] = None
        
        suggestions.append(suggestion)
    
    # If we need more suggestions than historical results, generate interpolated ones
    while len(suggestions) < n_suggestions and len(sorted_results) >= 2:
        suggestion = {}
        # Interpolate between top 2 configs
        config1 = sorted_results[0]["hyperparameters"]
        config2 = sorted_results[1]["hyperparameters"]
        
        for param in target_params:
            if param in config1 and param in config2:
                val1, val2 = config1[param], config2[param]
                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    suggestion[param] = (val1 + val2) / 2
                else:
                    suggestion[param] = val1
            elif param in config1:
                suggestion[param] = config1[param]
            elif param in config2:
                suggestion[param] = config2[param]
            else:
                suggestion[param] = None
        
        suggestions.append(suggestion)
    
    # Build rationale
    best_result = sorted_results[0]["result"]
    rationale = f"""Based on analysis of {len(historical_results)} historical optimization runs:
- Best result: {best_result} ({result_type})
- Top configuration: {json.dumps(best_config, indent=2)}
- Suggestions incorporate small variations around top-performing configurations
- New parameters (not in historical data) are marked as None and need specification
"""
    
    confidence = min(0.9, 0.5 + (len(historical_results) / 20))  # More data = higher confidence
    
    return {
        "suggestions": suggestions,
        "rationale": rationale,
        "confidence": confidence,
        "historical_best": {
            "experiment_id": sorted_results[0]["experiment_id"],
            "hyperparameters": best_config,
            "result": best_result
        }
    }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available hyperparameter advisor tools"""
    tools = [
        Tool(
            name="hyperparam_inject",
            description="""Inject hyperparameter optimization results into RAG for future suggestions.
            
Store historical optimization data including hyperparameter configurations and their results.
This data will be used to generate intelligent suggestions for future optimization runs.

Supports variable dimensions - you can inject results with different numbers of hyperparameters,
and later request suggestions with more or fewer parameters.

Use this tool to build up a knowledge base of optimization results over time.""",
            inputSchema={
                "type": "object",
                "required": ["results", "experiment_id"],
                "properties": {
                    "results": {
                        "type": "array",
                        "description": "List of hyperparameter-result pairs",
                        "items": {
                            "type": "object",
                            "required": ["hyperparameters", "result"],
                            "properties": {
                                "hyperparameters": {
                                    "type": "object",
                                    "description": "Hyperparameter names and values (e.g., {'learning_rate': 0.001, 'batch_size': 32})"
                                },
                                "result": {
                                    "type": "number",
                                    "description": "Optimization result metric (e.g., accuracy, loss, F1)"
                                },
                                "result_type": {
                                    "type": "string",
                                    "enum": ["maximize", "minimize"],
                                    "description": "Whether to maximize or minimize this metric",
                                    "default": "maximize"
                                },
                                "metadata": {
                                    "type": "object",
                                    "description": "Optional metadata (model name, dataset, etc.)"
                                }
                            }
                        }
                    },
                    "experiment_id": {
                        "type": "string",
                        "description": "Unique identifier for this experiment/optimization run"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["global", "private"],
                        "description": "Data visibility scope",
                        "default": "private"
                    }
                }
            }
        ),
        Tool(
            name="hyperparam_suggest",
            description="""Generate hyperparameter suggestions based on historical optimization results stored in RAG.
            
Analyzes past optimization runs and suggests promising hyperparameter configurations.
Handles variable dimensions - can suggest values for parameters not present in historical data.

The tool retrieves relevant historical results from RAG, analyzes patterns, and generates
diverse suggestions with explanations. Perfect for:
- Starting new optimization runs with informed initial guesses
- Exploring promising regions of hyperparameter space
- Handling new hyperparameters not seen in previous experiments

Returns multiple suggestions with rationale and confidence scores.""",
            inputSchema={
                "type": "object",
                "required": ["target_params"],
                "properties": {
                    "target_params": {
                        "type": "array",
                        "description": "List of hyperparameter names to suggest values for",
                        "items": {"type": "string"},
                        "example": ["learning_rate", "batch_size", "dropout", "optimizer"]
                    },
                    "experiment_id": {
                        "type": "string",
                        "description": "Filter suggestions to specific experiment (optional)"
                    },
                    "current_params": {
                        "type": "object",
                        "description": "Current hyperparameters for reference (optional)"
                    },
                    "result_type": {
                        "type": "string",
                        "enum": ["maximize", "minimize"],
                        "description": "Whether to maximize or minimize the result",
                        "default": "maximize"
                    },
                    "n_suggestions": {
                        "type": "integer",
                        "description": "Number of configurations to suggest (1-10)",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 3
                    },
                    "search_k": {
                        "type": "integer",
                        "description": "Number of historical results to retrieve (1-50)",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10
                    },
                    "constraints": {
                        "type": "object",
                        "description": """Optional parameter constraints. Supports both numeric and categorical parameters:
- Numeric: {"learning_rate": {"min": 0.0001, "max": 0.1}}
- Categorical: {"optimizer": {"choices": ["adam", "sgd", "rmsprop"]}}
- Mixed: {"learning_rate": {"min": 0.001, "max": 0.1, "default": 0.01}, "optimizer": {"choices": ["adam", "sgd"]}}"""
                    }
                }
            }
        )
    ]
    
    # Add LangGraph-based tool if available
    try:
        from hyperparam_mcp_integration import get_mcp_integration
        mcp_integration = get_mcp_integration()
        if mcp_integration.is_available():
            langgraph_tool = mcp_integration.get_tool_description()
            tools.append(Tool(
                name=langgraph_tool["name"],
                description=langgraph_tool["description"],
                inputSchema=langgraph_tool["inputSchema"]
            ))
            logger.info("LangGraph-based hyperparameter tool registered")
    except Exception as e:
        logger.warning(f"LangGraph tool not available: {e}")
    
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "hyperparam_inject":
            # Extract arguments
            results = arguments.get("results", [])
            experiment_id = arguments.get("experiment_id")
            scope = arguments.get("scope", "private")
            
            if not results or not experiment_id:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": "Missing required fields: results and experiment_id"
                    })
                )]
            
            # Format documents for RAG
            documents = []
            for result in results:
                hyperparams = result.get("hyperparameters", {})
                result_value = result.get("result", 0.0)
                result_type = result.get("result_type", "maximize")
                metadata = result.get("metadata")
                
                doc_text = format_hyperparam_doc(
                    hyperparams, result_value, experiment_id, result_type, metadata
                )
                documents.append(doc_text)
            
            # Inject to RAG
            inject_result = await inject_to_rag(documents, scope)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "message": f"Injected {len(documents)} hyperparameter results",
                    "experiment_id": experiment_id,
                    "count": len(documents),
                    "scope": scope
                }, indent=2)
            )]
        
        elif name == "hyperparam_suggest":
            # Extract arguments
            target_params = arguments.get("target_params", [])
            experiment_id = arguments.get("experiment_id")
            current_params = arguments.get("current_params")
            result_type = arguments.get("result_type", "maximize")
            n_suggestions = arguments.get("n_suggestions", 3)
            search_k = arguments.get("search_k", 10)
            constraints = arguments.get("constraints")
            
            if not target_params:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": "target_params is required"
                    })
                )]
            
            # Build RAG query
            query_parts = ["hyperparameter optimization"]
            if experiment_id:
                query_parts.append(f"experiment {experiment_id}")
            query_parts.append(f"result_type {result_type}")
            query = " ".join(query_parts)
            
            # Query RAG for historical results
            rag_docs = await query_rag(query, k=search_k)
            historical_results = parse_rag_results(rag_docs)
            
            if not historical_results:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": "No historical results found. Please inject optimization results first.",
                        "suggestions": [],
                        "historical_count": 0
                    }, indent=2)
                )]
            
            # Try LLM-based analysis first if enabled
            suggestion_data = None
            if USE_LLM_ANALYSIS:
                logger.info("Using LLM-based analysis for suggestions")
                suggestion_data = await llm_analyze_and_suggest(
                    historical_results=historical_results,
                    target_params=target_params,
                    result_type=result_type,
                    n_suggestions=n_suggestions,
                    constraints=constraints,
                    current_params=current_params
                )
                
                if suggestion_data:
                    logger.info("LLM analysis successful")
                else:
                    logger.warning("LLM analysis failed, falling back to heuristics")
            
            # Fallback to heuristic-based suggestions if LLM disabled or failed
            if not suggestion_data:
                logger.info("Using heuristic-based suggestions")
                suggestion_data = generate_suggestions(
                    historical_results=historical_results,
                    target_params=target_params,
                    result_type=result_type,
                    n_suggestions=n_suggestions,
                    constraints=constraints
                )
            
            # Add method used
            suggestion_data["method"] = "llm" if USE_LLM_ANALYSIS and suggestion_data.get("insights") else "heuristic"
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "suggestions": suggestion_data["suggestions"],
                    "rationale": suggestion_data["rationale"],
                    "confidence": suggestion_data["confidence"],
                    "historical_best": suggestion_data.get("historical_best"),
                    "historical_count": len(historical_results),
                    "insights": suggestion_data.get("insights", []),
                    "method": suggestion_data.get("method", "heuristic")
                }, indent=2)
            )]
        
        elif name == "hyperparam_suggest_with_skill":
            # Handle LangGraph-based suggestion
            try:
                from hyperparam_mcp_integration import get_mcp_integration
                mcp_integration = get_mcp_integration()
                
                if not mcp_integration.is_available():
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "error": "LangGraph skill not available. Install langgraph package."
                        })
                    )]
                
                # Extract arguments
                problem_description = arguments.get("problem_description", "")
                parameter_space = arguments.get("parameter_space", {})
                current_best = arguments.get("current_best")
                optimization_goal = arguments.get("optimization_goal", "maximize")
                max_iterations = arguments.get("max_iterations", 3)
                
                if not problem_description or not parameter_space:
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "success": False,
                            "error": "problem_description and parameter_space are required"
                        })
                    )]
                
                # Call LangGraph skill
                result = await mcp_integration.suggest_with_skill(
                    problem_description=problem_description,
                    parameter_space=parameter_space,
                    current_best=current_best,
                    optimization_goal=optimization_goal,
                    max_iterations=max_iterations
                )
                
                # Format result
                formatted = await mcp_integration.format_result_for_mcp(result)
                
                return [TextContent(
                    type="text",
                    text=formatted
                )]
                
            except ImportError as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": f"LangGraph dependencies not available: {e}"
                    })
                )]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Unknown tool: {name}"
                })
            )]
    
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": str(e)
            })
        )]


async def main():
    """Main entry point"""
    logger.info("Starting Hyperparameter Advisor MCP Server")
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
