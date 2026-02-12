# LangGraph-Based Hyperparameter Optimization Skill

## Overview

A LangGraph-powered workflow for intelligent hyperparameter optimization that uses RAG to retrieve historical results and applies **LLM-based analysis** to suggest new parameters.

## Features

### 🤖 LLM-Driven Analysis
The skill uses a large language model to:
- **Analyze Historical Patterns**: Examines past experiments from RAG storage
- **Identify Relationships**: Discovers parameter interactions and trends
- **Apply ML Best Practices**: Leverages LLM knowledge of ML/optimization
- **Generate Diverse Suggestions**: Proposes multiple configurations with reasoning

### 📚 RAG Integration
- Retrieves historical optimization results from vector store
- Uses semantic search to find similar past experiments
- Provides context to LLM for informed suggestions

### 🎯 Intelligent Suggestions
- Validates suggestions against parameter constraints
- Ranks by LLM confidence scores
- Provides detailed reasoning and insights
- Handles categorical, numeric, and integer parameters
- Optional refinement loop for low-confidence suggestions

## Architecture

```
┌──────────────────────────────────────────────────────┐
│           LangGraph Workflow (StateGraph)            │
├──────────────────────────────────────────────────────┤
│                                                      │
│  retrieve_historical → analyze_with_llm              │
│                              ↓                       │
│                    extract_suggestions               │
│                              ↓                       │
│                       should_refine?                 │
│                    ┌─────────┴─────────┐            │
│                    │                   │            │
│                 refine           synthesize_results  │
│                    │                   ↓            │
│                    └──────→ analyze ──→ END         │
│                       (loop back)                    │
└──────────────────────────────────────────────────────┘
```

## State Machine

The workflow maintains a `HyperparamState` that tracks:

- **Input**: problem description, parameter space, current best, optimization goal
- **RAG Data**: historical results retrieved from vector store, RAG query used
- **LLM Analysis**: full LLM response with suggestions and rationale
- **Loop Control**: iteration count, max iterations, confidence threshold
- **Candidates**: validated suggestions, best suggestion
- **Output**: confidence score, insights, reasoning, final recommendations

## Usage

### Via MCP Tool

The skill is exposed as an MCP tool: `hyperparam_suggest_with_skill`

```python
# Example request
{
    "problem_description": "Neural network training for image classification",
    "parameter_space": {
        "learning_rate": {
            "type": "numeric",
            "min": 0.0001,
            "max": 0.1,
            "default": 0.001
        },
        "batch_size": {
            "type": "integer",
            "min": 16,
        "optimizer": {
            "type": "categorical",
            "choices": ["adam", "sgd", "rmsprop"],
            "default": "adam"
        },
        "dropout": {
            "type": "numeric",
            "min": 0.0,
            "max": 0.5,
            "default": 0.3
        }
    },
    "current_best": {
        "learning_rate": 0.001,
        "batch_size": 32,
        "optimizer": "adam",
        "dropout": 0.2
    },
    "optimization_goal": "maximize",
    "max_iterations": 2
}
```

### Direct API Usage

```python
from hyperparam_skill import create_hyperparam_skill

# Create skill instance
skill = create_hyperparam_skill(
    llm_api_url="http://backend:8000/v1/chat/completions",
    embedding_model="nomic-embed-text",
    collection_name="hyperparameter_embeddings",
    max_iterations=2
)

# Get suggestions
result = await skill.suggest_hyperparameters(
    problem_description="Optimize BERT fine-tuning for NLP task",
    parameter_space={
        "learning_rate": {"type": "numeric", "min": 1e-5, "max": 5e-4, "default": 5e-5},
        "warmup_steps": {"type": "integer", "min": 0, "max": 1000, "default": 500},
        "weight_decay": {"type": "numeric", "min": 0.0, "max": 0.1, "default": 0.01}
    },
    optimization_goal="maximize"
)

print(result["best_parameters"])
print(result["reasoning"])
print(result["insights"])
```

## LLM Analysis Process

### 1. Retrieve Historical Context
**What happens**: 
- Query RAG vector store with problem description
- Retrieve top 15 similar past experiments
- Include metadata: parameters, results, experiment IDs

### 2. LLM Analysis
**What the LLM receives**:
- Problem description and optimization goal
- Parameter space with types, bounds, defaults
- Current best configuration (if available)
- Historical results sorted by performance
- Task to generate diverse suggestions

**What the LLM provides**:
```json
{
  "suggestions": [
    {"learning_rate": 0.001, "batch_size": 64, "optimizer": "adam"},
    {"learning_rate": 0.0005, "batch_size": 128, "optimizer": "sgd"},
    {"learning_rate": 0.002, "batch_size": 32, "optimizer": "rmsprop"}
  ],
  "rationale": "Analysis of patterns and strategy explanation...",
  "confidence": 0.85,
  "insights": [
    "Higher batch sizes correlate with better performance",
- Parse JSON suggestions from LLM response
- Validate each suggestion against parameter constraints
- Apply type checking (categorical choices, numeric bounds)
- Use defaults for missing parameters
- Case-insensitive matching for categorical values

### 4. Refinement (Optional)
**When**: Confidence < 0.75 and iterations < max  
**Action**:
- Increment iteration counter
- Re-analyze with updated context
- Generate new suggestions based on previous results

### 5. Synthesize Final Results
**Output includes**:
- Best suggestion with confidence score
- Top 5 alternative configurations
- LLM reasoning and insights
- Metadata: iterations, historical data used, RAG query

## Response Format

```json
{
  "best_parameters": {
    "learning_rate": 0.003,
    "batch_size": 64,
    "optimizer": "adam",
    "dropout": 0.25
  },
  "confidence": 0.85,
  "reasoning": "The LLM identified that Adam optimizer with moderate learning rates...",
  "insights": [
    "Batch sizes 64-128 show best convergence",
    "Dropout 0.2-0.3 prevents overfitting",
    "Learning rate 0.001-0.005 is optimal for this task"
  ],
  "alternatives": [
    {"parameters": {"learning_rate": 0.001, ...}, "confidence": 0.82, "iteration": 0},
    {"parameters": {"learning_rate": 0.005, ...}, "confidence": 0.78, "iteration": 0}
  ],
  "iterations_run": 1,
  "total_suggestions": 3,
  "historical_data_used": 15,
  "rag_query": "Hyperparameter optimization: Neural network training for..."
}
```

## Parameter Types

### Numeric
```python
{
    "learning_rate": {
        "type": "numeric",
        "min": 0.0001,
        "max": 0.1,
        "default": 0.001  # Recommended
    }
}
```

### Categorical
```python
{
    "optimizer": {
        "type": "categorical",
        "choices": ["adam", "sgd", "rmsprop", "adagrad"],
        "default": "adam"  # Recommended
    }
}
```

### Integer
```python
{
    "batch_size": {
        "type": "integer",
        "min": 16,
        "max": 256,
        "default": 32  # Recommended
    }
}
```

## Configuration

### Environment Variables
```bash
# RAG configuration
DATABASE_URL=postgresql://...
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_EMBED_MODEL=nomic-embed-text

# LLM API for analysis
LLM_API_URL=http://backend:8000/v1/chat/completions

# Optimization settings
MAX_ITERATIONS=2  # For LLM refinement loops
```

### Skill Initialization
```python
skill = HyperparamOptimizationSkill(
    vector_store=vector_store,    # Optional RAG store
    llm_api_url=llm_api_url,      # Required for LLM analysis
    max_iterations=2              # Refinement iterations
)
```

## Dependencies

Required packages (in `requirements.txt`):
```
langgraph>=0.2.0
langchain-core>=0.3.0
langchain-ollama>=0.2.0
langchain-postgres>=0.0.12
httpx>=0.27.0
```

## Integration with MCP Server

The skill is automatically registered with the MCP server in `main.py`:

```python
# Tools are discovered at server startup
tools = list_tools()  # Includes hyperparam_suggest_with_skill if available

# Calls are routed to the skill
result = await hyperparam_integration.suggest_with_skill(...)
```

## Error Handling

### Missing Dependencies
```json
{
  "error": "LangGraph not available",
  "best_parameters": {},
  "reasoning": "LangGraph dependencies not installed"
}
```

### No Historical Data
- Skill still works without RAG data
- LLM uses parameter space knowledge and ML best practices
- Lower confidence scores expected

### Invalid Parameters
```json
{
  "error": "parameter_space is required",
  "best_parameters": {}
}
```

## Best Practices

### 1. Build Historical Data
Before using the skill, inject past optimization results:
```python
# First, inject historical results
inject_result = await inject_to_rag([
    {
        "hyperparameters": {"lr": 0.001, "batch": 32},
        "result": 0.92,
        "result_type": "maximize"
    },
    # ... more results
])

# Then get suggestions
suggestions = await skill.suggest_hyperparameters(...)
```

### 2. Define Complete Parameter Space
Include all parameters you want suggestions for:
```python
parameter_space = {
    "learning_rate": {"type": "numeric", "min": 1e-5, "max": 1e-3},
    "batch_size": {"type": "integer", "min": 16, "max": 128},
    "optimizer": {"type": "categorical", "choices": ["adam", "sgd"]},
    # ... all parameters
}
```

### 3. Use Appropriate Iterations
- `max_iterations=1`: Quick single-method suggestion
- `max_iterations=3`: Balanced exploration (recommended)
- `max_iterations=5+`: Thorough search (slower)

### 4. Provide Context
Include problem description and current best:
```python
{
    "problem_description": "BERT fine-tuning for sentiment analysis on IMDB dataset",
    "current_best": {...},  # Your current best config
    "optimization_goal": "maximize"
}
```

## Performance

- **Typical latency**: 2-5 seconds for 3 iterations
- **Candidates generated**: 3-5 per method
- **RAG queries**: 1 per workflow (10 results)
- **Memory usage**: ~100MB for workflow state

## Limitations

1. **No Auto-Tuning**: Doesn't automatically run experiments, only suggests parameters
2. **Synchronous Methods**: Methods run sequentially, not in parallel
3. **Simple Scoring**: Uses basic confidence scoring for candidates
4. **Fixed Method Order**: Methods always run in specified sequence

## Future Enhancements

- [ ] Parallel method execution
- [ ] Adaptive method selection based on convergence
- [ ] Multi-objective optimization support
- [ ] Constraint satisfaction handling
- [ ] Integration with experiment tracking (MLflow, W&B)
- [ ] Automated hyperparameter tuning loops

## Related Documentation

- [Hyperparameter Advisor Service](README.md)
- [Categorical Parameter Support](CATEGORICAL_GUIDE.md)
- [Service Migration](MIGRATION.md)
- [MCP Integration](hyperparam_mcp_integration.py)

## Example Workflow

```python
# 1. Create skill
skill = create_hyperparam_skill(max_iterations=3)

# 2. Define problem
problem = {
    "problem_description": "CNN training for CIFAR-10",
    "parameter_space": {
        "learning_rate": {"type": "numeric", "min": 0.0001, "max": 0.01},
        "momentum": {"type": "numeric", "min": 0.0, "max": 0.99},
        "weight_decay": {"type": "numeric", "min": 0.0, "max": 0.001},
        "optimizer": {"type": "categorical", "choices": ["sgd", "adam"]},
        "batch_size": {"type": "integer", "min": 32, "max": 256}
    },
    "optimization_goal": "maximize"
}

# 3. Get suggestions
result = await skill.suggest_hyperparameters(**problem)

# 4. Use best suggestion
best = result["best_parameters"]
print(f"Try: lr={best['learning_rate']}, batch={best['batch_size']}")
print(f"Confidence: {result['confidence']}")
print(f"\nReasoning:\n{result['reasoning']}")

# 5. Run experiment with suggested parameters
# accuracy = train_model(**best)

# 6. Inject result back to RAG for future suggestions
# await inject_to_rag([{
#     "hyperparameters": best,
#     "result": accuracy,
#     "result_type": "maximize"
# }])
```

## Troubleshooting

### Skill not available
**Issue**: `LangGraph skill not available`  
**Solution**: Install dependencies: `pip install langgraph>=0.2.0`

### No suggestions generated
**Issue**: Empty suggestions list  
**Solution**: Inject historical results first using `hyperparam_inject` tool

### Poor quality suggestions
**Issue**: Suggestions don't improve performance  
**Solution**: 
- Inject more historical data (50+ results recommended)
- Check parameter space bounds are reasonable
- Verify optimization goal is correct (maximize vs minimize)

### High latency
**Issue**: Suggestions take >10 seconds  
**Solution**:
- Reduce `max_iterations` (use 1-2)
- Reduce `search_k` for RAG queries (use 5-10)
- Check database connection latency
