#!/usr/bin/env python3
"""
LangGraph-based Hyperparameter Optimization Skill

Uses RAG to retrieve historical optimization results and LLM-based analysis
to provide intelligent hyperparameter suggestions.

This skill constructs a workflow that:
1. Retrieves relevant historical results from RAG
2. Analyzes patterns using LLM
3. Generates informed suggestions with detailed reasoning
"""

import os
import logging
from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime
import json

try:
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None

logger = logging.getLogger("hyperparam_skill")

# Try to import RAG utilities
try:
    from rag_common import get_vector_store_for_model, LANGCHAIN_AVAILABLE
except ImportError:
    LANGCHAIN_AVAILABLE = False
    get_vector_store_for_model = None


class HyperparamState(TypedDict):
    """State for hyperparameter optimization workflow"""
    # Input
    problem_description: str
    parameter_space: Dict[str, Any]  # Define search space for each parameter
    current_best: Optional[Dict[str, Any]]  # Best known hyperparameters
    optimization_goal: str  # "maximize" or "minimize"
    
    # RAG retrieval
    historical_results: List[Dict[str, Any]]  # Retrieved from RAG
    rag_query: str  # Query used for retrieval
    
    # LLM Analysis
    llm_analysis: Optional[Dict[str, Any]]  # LLM analysis results
    insights: List[str]  # Key insights from analysis
    
    # Iterations for refinement
    iteration: int
    max_iterations: int
    
    # Suggestions
    candidate_suggestions: List[Dict[str, Any]]
    best_suggestion: Optional[Dict[str, Any]]
    
    # Results
    confidence: float
    reasoning: str
    final_output: str


class HyperparamOptimizationSkill:
    """LangGraph skill for LLM-based hyperparameter optimization"""
    
    def __init__(
        self,
        vector_store=None,
        llm_api_url: str = None,
        max_iterations: int = 2
    ):
        """
        Initialize the hyperparameter optimization skill
        
        Args:
            vector_store: RAG vector store for retrieving historical results
            llm_api_url: URL for LLM API endpoint
            max_iterations: Maximum refinement iterations (default: 2)
        """
        self.vector_store = vector_store
        self.llm_api_url = llm_api_url or os.getenv("LLM_API_URL", "http://localhost:4000/v1/chat/completions")
        self.max_iterations = max_iterations
        
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph is required for this skill")
        
        # Build the optimization graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for LLM-based hyperparameter optimization"""
        workflow = StateGraph(HyperparamState)
        
        # Add nodes for each step
        workflow.add_node("retrieve_historical", self._retrieve_historical)
        workflow.add_node("analyze_with_llm", self._analyze_with_llm)
        workflow.add_node("extract_suggestions", self._extract_suggestions)
        workflow.add_node("refine_suggestions", self._refine_suggestions)
        workflow.add_node("synthesize_results", self._synthesize_results)
        
        # Define linear workflow with optional refinement loop
        workflow.set_entry_point("retrieve_historical")
        workflow.add_edge("retrieve_historical", "analyze_with_llm")
        workflow.add_edge("analyze_with_llm", "extract_suggestions")
        
        # Conditional: refine or finalize
        workflow.add_conditional_edges(
            "extract_suggestions",
            self._should_refine,
            {
                "refine": "refine_suggestions",
                "finish": "synthesize_results"
            }
        )
        
        # After refinement, loop back to LLM analysis or finish
        workflow.add_conditional_edges(
            "refine_suggestions",
            self._should_continue_refining,
            {
                "continue": "analyze_with_llm",
                "finish": "synthesize_results"
            }
        )
        
        workflow.add_edge("synthesize_results", END)
        
        return workflow.compile()
    
    def _retrieve_historical(self, state: HyperparamState) -> HyperparamState:
        """Retrieve historical optimization results from RAG"""
        logger.info("Retrieving historical results from RAG...")
        
        historical_results = []
        
        if self.vector_store and LANGCHAIN_AVAILABLE:
            try:
                # Build query from problem description and parameters
                query_parts = [f"Hyperparameter optimization: {state['problem_description']}"]
                if state.get('current_best'):
                    query_parts.append(f"Similar to {state['current_best']}")
                query_parts.append(f"Goal: {state['optimization_goal']}")
                
                query = " ".join(query_parts)
                state["rag_query"] = query
                
                # Search for similar optimization problems
                docs = self.vector_store.similarity_search(query, k=15)
                
                for doc in docs:
                    try:
                        # Parse metadata and content
                        result_data = {
                            "content": doc.page_content,
                            "metadata": doc.metadata,
                            "score": getattr(doc, 'score', 0.0)
                        }
                        historical_results.append(result_data)
                    except Exception as e:
                        logger.warning(f"Error parsing document: {e}")
                
                logger.info(f"Retrieved {len(historical_results)} historical results")
            except Exception as e:
                logger.error(f"Error retrieving from RAG: {e}")
        
        state["historical_results"] = historical_results
        state["iteration"] = 0
        state["candidate_suggestions"] = []
        state["insights"] = []
        
        return state
    
    async def _analyze_with_llm(self, state: HyperparamState) -> HyperparamState:
        """Analyze historical results using LLM to generate insights and suggestions"""
        logger.info("Analyzing with LLM...")
        
        import httpx
        
        historical_results = state["historical_results"]
        parameter_space = state["parameter_space"]
        optimization_goal = state["optimization_goal"]
        problem_desc = state["problem_description"]
        current_best = state.get("current_best")
        
        # Build comprehensive prompt for LLM
        prompt = self._build_analysis_prompt(
            problem_desc=problem_desc,
            historical_results=historical_results,
            parameter_space=parameter_space,
            optimization_goal=optimization_goal,
            current_best=current_best,
            iteration=state["iteration"]
        )
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.llm_api_url,
                    json={
                        "model": "rag-agent",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an expert ML hyperparameter optimization advisor. "
                                          "Analyze historical optimization data and provide detailed, "
                                          "actionable suggestions based on patterns and best practices."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2500
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Parse JSON from response
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    llm_analysis = json.loads(content)
                    state["llm_analysis"] = llm_analysis
                    state["insights"] = llm_analysis.get("insights", [])
                    
                    logger.info(f"LLM analysis complete with {len(llm_analysis.get('suggestions', []))} suggestions")
                else:
                    logger.error(f"LLM API error: {response.status_code}")
                    state["llm_analysis"] = None
                    
        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}", exc_info=True)
            state["llm_analysis"] = None
        
        return state
    
    def _build_analysis_prompt(
        self,
        problem_desc: str,
        historical_results: List[Dict[str, Any]],
        parameter_space: Dict[str, Any],
        optimization_goal: str,
        current_best: Optional[Dict[str, Any]],
        iteration: int
    ) -> str:
        """Build comprehensive prompt for LLM analysis"""
        
        prompt = f"""Analyze hyperparameter optimization data and suggest promising configurations.

**Problem**: {problem_desc}
**Optimization Goal**: {optimization_goal.upper()}
**Analysis Iteration**: {iteration + 1}

**Parameter Space**:
"""
        
        for param_name, param_config in parameter_space.items():
            param_type = param_config.get("type", "numeric")
            prompt += f"\n  - {param_name} ({param_type}):"
            if "choices" in param_config:
                prompt += f" choices={param_config['choices']}"
            else:
                if "min" in param_config:
                    prompt += f" min={param_config['min']}"
                if "max" in param_config:
                    prompt += f" max={param_config['max']}"
            if "default" in param_config:
                prompt += f" default={param_config['default']}"
        
        if current_best:
            prompt += f"\n\n**Current Best Configuration**:\n{json.dumps(current_best, indent=2)}"
        
        if historical_results:
            prompt += f"\n\n**Historical Optimization Results** ({len(historical_results)} entries):\n"
            
            # Sort and show top results
            sorted_results = sorted(
                [r for r in historical_results if "result" in r.get("metadata", {})],
                key=lambda x: x["metadata"].get("result", 0),
                reverse=(optimization_goal == "maximize")
            )[:10]
            
            for i, result in enumerate(sorted_results, 1):
                metadata = result.get("metadata", {})
                prompt += f"\n{i}. Result: {metadata.get('result', 'N/A')}"
                if "experiment_id" in metadata:
                    prompt += f" (Experiment: {metadata['experiment_id']})"
                hyperparams = metadata.get("hyperparameters", {})
                if hyperparams:
                    prompt += f"\n   Parameters: {json.dumps(hyperparams)}"
        else:
            prompt += "\n\n**Historical Results**: No historical data available."
        
        prompt += f"""

**Task**: Provide {3 if iteration == 0 else 2} diverse hyperparameter suggestions.

Consider:
1. **Pattern Recognition**: What configurations performed best historically?
2. **Parameter Interactions**: How do parameters relate to each other?
3. **Constraints**: Respect type constraints (categorical choices, numeric bounds)
4. **Exploration vs Exploitation**: Balance trying new values with refining known good configs
5. **Diversity**: Ensure suggestions explore different regions
6. **Best Practices**: Apply ML/optimization knowledge for parameters without historical data

**Output Format** (JSON only):
{{
  "suggestions": [
    {{"param1": value1, "param2": value2, ...}},
    {{"param1": value3, "param2": value4, ...}},
    ...
  ],
  "rationale": "Detailed explanation of patterns observed and strategy behind suggestions",
  "confidence": 0.85,
  "insights": [
    "Key insight about parameter relationships",
    "Observation about successful configurations",
    "Recommendation for future experiments"
  ]
}}

Respond with ONLY the JSON object."""
        
        return prompt
    
    def _extract_suggestions(self, state: HyperparamState) -> HyperparamState:
        """Extract and validate suggestions from LLM analysis"""
        logger.info("Extracting suggestions from LLM analysis...")
        
        llm_analysis = state.get("llm_analysis")
        
        if not llm_analysis:
            logger.warning("No LLM analysis available")
            return state
        
        suggestions = llm_analysis.get("suggestions", [])
        parameter_space = state["parameter_space"]
        
        # Validate and apply constraints
        validated_suggestions = []
        for suggestion in suggestions:
            validated = self._validate_suggestion(suggestion, parameter_space)
            if validated:
                validated_suggestions.append({
                    "parameters": validated,
                    "method": "llm_analysis",
                    "confidence": llm_analysis.get("confidence", 0.7),
                    "iteration": state["iteration"]
                })
        
        state["candidate_suggestions"].extend(validated_suggestions)
        
        # Select best based on confidence
        if validated_suggestions:
            best = max(validated_suggestions, key=lambda x: x["confidence"])
            state["best_suggestion"] = best
        
        state["reasoning"] = llm_analysis.get("rationale", "")
        state["confidence"] = llm_analysis.get("confidence", 0.7)
        
        logger.info(f"Extracted {len(validated_suggestions)} validated suggestions")
        
        return state
    
    def _validate_suggestion(
        self,
        suggestion: Dict[str, Any],
        parameter_space: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Validate and constrain a suggestion to parameter space"""
        
        validated = {}
        
        for param_name, param_config in parameter_space.items():
            if param_name not in suggestion:
                # Missing parameter - use default if available
                if "default" in param_config:
                    validated[param_name] = param_config["default"]
                elif "choices" in param_config and param_config["choices"]:
                    validated[param_name] = param_config["choices"][0]
                else:
                    logger.warning(f"Missing parameter {param_name} in suggestion")
                    return None
                continue
            
            value = suggestion[param_name]
            param_type = param_config.get("type", "numeric")
            
            if param_type == "categorical":
                # Validate categorical choice
                choices = param_config.get("choices", [])
                if value not in choices:
                    # Try case-insensitive match
                    if isinstance(value, str):
                        lower_choices = {str(c).lower(): c for c in choices}
                        matched = lower_choices.get(value.lower())
                        if matched:
                            validated[param_name] = matched
                        else:
                            # Use first valid choice
                            validated[param_name] = choices[0] if choices else value
                    else:
                        validated[param_name] = choices[0] if choices else value
                else:
                    validated[param_name] = value
            
            elif param_type in ("numeric", "integer"):
                # Apply numeric bounds
                val = value
                if "min" in param_config:
                    val = max(val, param_config["min"])
                if "max" in param_config:
                    val = min(val, param_config["max"])
                
                if param_type == "integer":
                    val = int(round(val))
                
                validated[param_name] = val
            else:
                # String or other type - pass through
                validated[param_name] = value
        
        return validated
    
    def _should_refine(self, state: HyperparamState) -> str:
        """Decide whether to refine suggestions"""
        # Refine if we have low confidence and haven't reached max iterations
        if state["confidence"] < 0.75 and state["iteration"] < state["max_iterations"] - 1:
            return "refine"
        return "finish"
    
    def _refine_suggestions(self, state: HyperparamState) -> HyperparamState:
        """Prepare state for refinement iteration"""
        logger.info("Preparing for refinement iteration...")
        state["iteration"] += 1
        return state
    
    def _should_continue_refining(self, state: HyperparamState) -> str:
        """Check if we should continue refining"""
        if state["iteration"] >= state["max_iterations"]:
            return "finish"
        return "continue"
    
    def _synthesize_results(self, state: HyperparamState) -> HyperparamState:
        """Synthesize final results and recommendations"""
        logger.info("Synthesizing final results...")
        
        best = state.get("best_suggestion")
        candidates = state["candidate_suggestions"]
        insights = state.get("insights", [])
        reasoning = state.get("reasoning", "")
        
        if best:
            recommendations = {
                "best_parameters": best["parameters"],
                "confidence": state.get("confidence", best.get("confidence", 0)),
                "reasoning": reasoning,
                "insights": insights,
                "alternatives": [
                    {
                        "parameters": c["parameters"],
                        "confidence": c.get("confidence", 0),
                        "iteration": c.get("iteration", 0)
                    }
                    for c in candidates[:5]  # Top 5 alternatives
                ],
                "iterations_run": state["iteration"] + 1,
                "total_suggestions": len(candidates),
                "historical_data_used": len(state.get("historical_results", [])),
                "rag_query": state.get("rag_query", "")
            }
        else:
            recommendations = {
                "best_parameters": {},
                "confidence": 0,
                "reasoning": "No suitable suggestions could be generated",
                "insights": insights,
                "alternatives": [],
                "message": "No suitable suggestions generated"
            }
        
        state["final_recommendations"] = recommendations
        return state
    
    async def suggest_hyperparameters(
        self,
        problem_description: str,
        parameter_space: Dict[str, Any],
        optimization_goal: str = "maximize",
        current_best: Optional[Dict[str, Any]] = None,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        Main entry point for hyperparameter suggestion using LLM-based analysis.
        
        Args:
            problem_description: Description of the optimization problem
            parameter_space: Dict defining parameter types, ranges, choices
            optimization_goal: "maximize" or "minimize"
            current_best: Optional current best configuration
            max_iterations: Maximum refinement iterations (default 2)
            
        Returns:
            Dict with recommendations and metadata
            
        Example parameter_space:
            {
                "learning_rate": {"type": "numeric", "min": 0.0001, "max": 0.1, "default": 0.001},
                "batch_size": {"type": "integer", "min": 8, "max": 128, "default": 32},
                "optimizer": {"type": "categorical", "choices": ["adam", "sgd", "rmsprop"], "default": "adam"}
            }
        """
        initial_state = HyperparamState(
            problem_description=problem_description,
            parameter_space=parameter_space,
            optimization_goal=optimization_goal,
            current_best=current_best,
            max_iterations=max_iterations,
            iteration=0,
            historical_results=[],
            candidate_suggestions=[],
            llm_analysis=None,
            insights=[],
            rag_query="",
            confidence=0.0,
            best_suggestion=None,
            final_recommendations=None,
            reasoning=""
        )
        
        try:
            logger.info(f"Starting LLM-based hyperparameter optimization: {problem_description}")
            result = await self.workflow.ainvoke(initial_state)
            return result.get("final_recommendations", {})
        except Exception as e:
            logger.error(f"Error in hyperparameter optimization: {e}", exc_info=True)
            return {
                "best_parameters": {},
                "confidence": 0,
                "reasoning": f"Error during optimization: {str(e)}",
                "insights": [],
                "alternatives": [],
                "error": str(e)
            }



# Factory function to create the skill
def create_hyperparam_skill(
    llm_api_url: str,
    embedding_model: str = "nomic-embed-text",
    collection_name: str = "hyperparameter_embeddings",
    max_iterations: int = 2
) -> Optional[HyperparamOptimizationSkill]:
    """
    Create and return a hyperparameter optimization skill instance
    
    Args:
        llm_api_url: URL to the LLM API endpoint
        embedding_model: Name of the embedding model
        collection_name: Vector store collection name
        max_iterations: Maximum refinement iterations (default 2 for LLM-based)
    
    Returns:
        HyperparamOptimizationSkill instance or None if dependencies unavailable
    """
    if not LANGGRAPH_AVAILABLE:
        logger.error("LangGraph not available, cannot create skill")
        return None
    
    vector_store = None
    if LANGCHAIN_AVAILABLE and get_vector_store_for_model:
        try:
            vector_store = get_vector_store_for_model(embedding_model, collection_name)
            logger.info("Vector store initialized for hyperparameter skill")
        except Exception as e:
            logger.warning(f"Could not initialize vector store: {e}")
    
    return HyperparamOptimizationSkill(
        vector_store=vector_store,
        llm_api_url=llm_api_url,
        max_iterations=max_iterations
    )

