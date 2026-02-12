#!/usr/bin/env python3
"""
MCP Integration for LangGraph Hyperparameter Skill

Exposes the LangGraph-based hyperparameter optimization skill as MCP tools.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hyperparam_mcp_integration")

try:
    from hyperparam_skill import create_hyperparam_skill, LANGGRAPH_AVAILABLE
except ImportError:
    LANGGRAPH_AVAILABLE = False
    create_hyperparam_skill = None


class HyperparamMCPIntegration:
    """Integration layer between MCP server and LangGraph skill"""
    
    def __init__(self, llm_api_url: Optional[str] = None):
        """
        Initialize the MCP integration
        
        Args:
            llm_api_url: URL to the LLM API endpoint (defaults to env var LLM_API_URL)
        """
        self.skill = None
        self.llm_api_url = llm_api_url or os.getenv("LLM_API_URL", "http://backend:8000/v1/chat/completions")
        
        if LANGGRAPH_AVAILABLE and create_hyperparam_skill:
            try:
                self.skill = create_hyperparam_skill(
                    llm_api_url=self.llm_api_url,
                    max_iterations=2
                )
                logger.info(f"Hyperparameter optimization skill initialized with LLM API: {self.llm_api_url}")
            except Exception as e:
                logger.error(f"Failed to initialize skill: {e}")
    
    def is_available(self) -> bool:
        """Check if the skill is available"""
        return self.skill is not None
    
    async def suggest_with_skill(
        self,
        problem_description: str,
        parameter_space: Dict[str, Any],
        current_best: Optional[Dict[str, Any]] = None,
        optimization_goal: str = "maximize",
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Use LangGraph skill to suggest hyperparameters
        
        Args:
            problem_description: Description of the optimization problem
            parameter_space: Dictionary defining search space
            current_best: Optional current best parameters
            optimization_goal: "maximize" or "minimize"
            max_iterations: Number of optimization iterations
        
        Returns:
            Suggestion results with reasoning
        """
        if not self.skill:
            return {
                "error": "LangGraph skill not available",
                "best_parameters": {},
                "reasoning": "LangGraph dependencies not installed"
            }
        
        try:
            # Update max iterations if specified
            if max_iterations != self.skill.max_iterations:
                self.skill.max_iterations = max_iterations
            
            result = await self.skill.suggest_hyperparameters(
                problem_description=problem_description,
                parameter_space=parameter_space,
                current_best=current_best,
                optimization_goal=optimization_goal
            )
            
            return result
        except Exception as e:
            logger.error(f"Error in LangGraph suggestion: {e}", exc_info=True)
            return {
                "error": str(e),
                "best_parameters": {},
                "reasoning": f"Error during optimization: {e}"
            }
    
    def get_tool_description(self) -> Dict[str, Any]:
        """Get MCP tool description for the LangGraph skill"""
        return {
            "name": "hyperparam_suggest_with_skill",
            "description": """
Advanced hyperparameter optimization using LangGraph workflow.

Uses multiple optimization methods in sequence (Bayesian, Random, Grid Search)
and retrieves historical results from RAG to inform suggestions.

This tool implements an intelligent multi-method optimization loop that:
1. Retrieves similar past optimization results from RAG
2. Applies different optimization methods iteratively
3. Evaluates and ranks candidate suggestions
4. Returns the best parameters with detailed reasoning

Methods used:
- Bayesian: Perturbs around best historical results
- Random: Explores parameter space randomly
- Grid: Systematically samples parameter grid
- Gradient: Small steps around current best

Parameters should include:
- problem_description: What you're optimizing
- parameter_space: Dict with parameter definitions
  Example: {
    "learning_rate": {"type": "numeric", "min": 0.0001, "max": 0.1},
    "optimizer": {"type": "categorical", "choices": ["adam", "sgd", "rmsprop"]},
    "batch_size": {"type": "integer", "min": 16, "max": 256}
  }
- current_best (optional): Current best known parameters
- optimization_goal: "maximize" or "minimize"
- max_iterations: Number of optimization loops (default: 3)
""".strip(),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "problem_description": {
                        "type": "string",
                        "description": "Description of the optimization problem"
                    },
                    "parameter_space": {
                        "type": "object",
                        "description": "Parameter space definition with types and ranges",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["numeric", "categorical", "integer", "string"]
                                },
                                "min": {"type": "number"},
                                "max": {"type": "number"},
                                "choices": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    },
                    "current_best": {
                        "type": "object",
                        "description": "Current best hyperparameters (optional)",
                        "additionalProperties": True
                    },
                    "optimization_goal": {
                        "type": "string",
                        "enum": ["maximize", "minimize"],
                        "description": "Optimization objective",
                        "default": "maximize"
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Number of optimization iterations",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["problem_description", "parameter_space"]
            }
        }
    
    async def format_result_for_mcp(self, result: Dict[str, Any]) -> str:
        """Format result for MCP response"""
        if "error" in result:
            return json.dumps({
                "status": "error",
                "error": result["error"],
                "message": result.get("reasoning", "Unknown error")
            }, indent=2)
        
        output = {
            "status": "success",
            "best_parameters": result.get("best_parameters", {}),
            "confidence": result.get("confidence", 0),
            "method": result.get("method", "unknown"),
            "alternatives": result.get("alternatives", []),
            "iterations_performed": result.get("iterations_performed", 0),
            "candidates_evaluated": result.get("candidates_evaluated", 0),
            "reasoning": result.get("reasoning", "")
        }
        
        return json.dumps(output, indent=2)


# Global instance
_mcp_integration = None


def get_mcp_integration() -> HyperparamMCPIntegration:
    """Get or create the global MCP integration instance"""
    global _mcp_integration
    if _mcp_integration is None:
        _mcp_integration = HyperparamMCPIntegration()
    return _mcp_integration
