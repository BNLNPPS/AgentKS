# Hyperparameter Advisor MCP Server

An MCP (Model Context Protocol) server that provides intelligent hyperparameter optimization suggestions based on historical results stored in RAG.

## Overview

This MCP server exposes tools for hyperparameter optimization workflows:

1. **hyperparam_inject**: Store optimization results in RAG
2. **hyperparam_suggest**: Get intelligent suggestions based on historical data

## Features

- **Variable Dimensions**: Handle cases where historical runs have different numbers of hyperparameters than current optimization
- **LLM-Powered Analysis**: Uses language models to analyze patterns and generate intelligent suggestions (with heuristic fallback)
- **Pattern Recognition**: Identifies trends in successful configurations and parameter interactions
- **Constraint Support**: Apply constraints to both numeric (min/max bounds) and categorical (allowed choices) parameters
- **Categorical Parameters**: Full support for categorical hyperparameters with discrete choices (e.g., optimizer types, activation functions)
- **Multiple Suggestions**: Generate diverse suggestions with detailed rationale
- **Confidence Scoring**: Provide confidence levels based on amount of historical data
- **Insights Generation**: Extract key insights about hyperparameter relationships from historical data

## Tools

### hyperparam_inject

Inject hyperparameter optimization results into RAG for future suggestions.

**Parameters:**
- `results` (array, required): List of hyperparameter-result pairs
  - `hyperparameters` (object): Parameter names and values
  - `result` (number): Optimization metric value
  - `result_type` (string): "maximize" or "minimize"
  - `metadata` (object, optional): Additional info
- `experiment_id` (string, required): Unique experiment identifier
- `scope` (string): "global" or "private" (default: "private")

**Example:**
```json
{
  "results": [
    {
      "hyperparameters": {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100
      },
      "result": 0.95,
      "result_type": "maximize"
    },
    {
      "hyperparameters": {
        "learning_rate": 0.01,
        "batch_size": 64,
        "epochs": 50
      },
      "result": 0.89,
      "result_type": "maximize"
    }
  ],
  "experiment_id": "mnist-optimization-2026-02",
  "scope": "private"
}
```

### hyperparam_suggest

Generate hyperparameter suggestions based on historical optimization results.

**Parameters:**
- `target_params` (array of strings, required): Parameter names to suggest values for
- `experiment_id` (string, optional): Filter to specific experiment
- `current_params` (object, optional): Current configuration for reference
- `result_type` (string): "maximize" or "minimize" (default: "maximize")
- `n_suggestions` (integer): Number of suggestions (1-10, default: 3)
- `search_k` (integer): Number of historical results to analyze (1-50, default: 10)
- `constraints` (object, optional): Parameter bounds

**Example:**
```json
{
  "target_params": [
    "learning_rate",
    "batch_size",
    "dropout",
    "optimizer",
    "activation"
  ],
  "experiment_id": "mnist-optimization-2026-02",
  "result_type": "maximize",
  "n_suggestions": 3,
  "constraints": {
    "learning_rate": {"min": 0.0001, "max": 0.1},
    "batch_size": {"min": 16, "max": 128},
    "optimizer": {"choices": ["adam", "sgd", "rmsprop", "adamw"]},
    "activation": {"choices": ["relu", "tanh", "sigmoid", "gelu"]}
  }
}
```

**Response:**
```json
{
  "success": true,
  "suggestions": [
    {
      "learning_rate": 0.001,
      "batch_size": 32,
      "dropout": 0.2,
      "optimizer": "adam",
      "activation": "relu"
    },
    {
      "learning_rate": 0.0015,
      "batch_size": 48,
      "dropout": 0.3,
      "optimizer": "adamw",
      "activation": "gelu"
    },
    {
      "learning_rate": 0.0008,
      "batch_size": 28,
      "dropout": 0.15,
      "optimizer": "sgd",
      "activation": "relu"
    }
  ],
  "rationale": "Based on analysis of 10 historical optimization runs, the top-performing configurations consistently use learning rates between 0.0008-0.001 with batch sizes of 28-48. Adam and AdamW optimizers outperformed SGD in 8 out of 10 runs. ReLU activation was most common in successful configs. For the new dropout parameter, values between 0.15-0.3 are recommended based on similar model architectures.",
  "confidence": 0.85,
  "historical_best": {
    "experiment_id": "mnist-optimization-2026-02",
    "hyperparameters": {
      "learning_rate": 0.001,
      "batch_size": 32,
      "epochs": 100,
      "optimizer": "adam",
      "activation": "relu"
    },
    "result": 0.95
  },
  "historical_count": 10,
  "insights": [
    "Lower learning rates (0.0008-0.001) consistently outperform higher values",
    "Batch size shows non-linear relationship with performance, peak at 32-48",
    "Adam optimizer provides 5% better results on average compared to SGD",
    "AdamW shows promise for preventing overfitting with similar performance to Adam",
    "ReLU activation dominates in successful configs (70% of top results)"
  ],
  "method": "llm"
}
```

## Categorical Hyperparameters

The tool fully supports categorical (discrete choice) hyperparameters alongside numeric parameters. Categorical parameters are commonly used for:

- **Optimizer types**: adam, sgd, rmsprop, adamw, etc.
- **Activation functions**: relu, tanh, sigmoid, gelu, etc.
- **Loss functions**: cross_entropy, mse, mae, etc.
- **Neural network architectures**: cnn, rnn, lstm, transformer
- **Normalization methods**: batch_norm, layer_norm, instance_norm
- **Any discrete choice**: on/off, true/false, strategy names, etc.

### Defining Categorical Constraints

Use the `choices` key in constraints to specify allowed values:

```json
{
  "constraints": {
    "optimizer": {
      "choices": ["adam", "sgd", "rmsprop", "adamw"]
    },
    "activation": {
      "choices": ["relu", "tanh", "sigmoid", "gelu"]
    },
    "use_dropout": {
      "choices": [true, false]
    }
  }
}
```

### How It Works

#### LLM-Based Analysis (Default)

When analyzing historical data with categorical parameters:

1. **Pattern Recognition**: The LLM identifies which categorical choices perform best
2. **Frequency Analysis**: Considers how often each choice appears in top results
3. **Contextual Selection**: Chooses values based on their relationship with other parameters
4. **Diversity**: Explores different categorical combinations across suggestions
5. **Validation**: Ensures all suggested values are in the allowed choices

#### Heuristic-Based (Fallback)

When LLM is unavailable:

1. **Frequency Counting**: Counts how often each choice appears in top 10 historical results
2. **Weighted Selection**: Prioritizes choices that appear more frequently in successful runs
3. **Exploration**: Rotates through less common choices for diversity
4. **Default Handling**: Uses first choice if no historical data exists for that parameter

### Example: Optimizing with Categorical Parameters

```python
# Inject historical results with categorical parameters
{
  "tool": "hyperparam_inject",
  "arguments": {
    "results": [
      {
        "hyperparameters": {
          "learning_rate": 0.001,
          "batch_size": 32,
          "optimizer": "adam",
          "activation": "relu",
          "use_batch_norm": true
        },
        "result": 0.95,
        "result_type": "maximize"
      },
      {
        "hyperparameters": {
          "learning_rate": 0.01,
          "batch_size": 64,
          "optimizer": "sgd",
          "activation": "tanh",
          "use_batch_norm": false
        },
        "result": 0.89,
        "result_type": "maximize"
      }
    ],
    "experiment_id": "my-experiment"
  }
}

# Get suggestions with categorical constraints
{
  "tool": "hyperparam_suggest",
  "arguments": {
    "target_params": [
      "learning_rate",
      "batch_size",
      "optimizer",
      "activation",
      "use_batch_norm"
    ],
    "n_suggestions": 3,
    "constraints": {
      "learning_rate": {"min": 0.0001, "max": 0.1},
      "batch_size": {"min": 16, "max": 128},
      "optimizer": {"choices": ["adam", "sgd", "rmsprop", "adamw"]},
      "activation": {"choices": ["relu", "tanh", "sigmoid", "gelu"]},
      "use_batch_norm": {"choices": [true, false]}
    }
  }
}

# Response includes intelligent categorical selections:
{
  "suggestions": [
    {
      "learning_rate": 0.001,
      "batch_size": 32,
      "optimizer": "adam",      # Most frequent in top results
      "activation": "relu",      # Most frequent in top results
      "use_batch_norm": true     # Associated with best result
    },
    {
      "learning_rate": 0.0015,
      "batch_size": 48,
      "optimizer": "adamw",      # Exploration of similar optimizer
      "activation": "gelu",      # Exploration of advanced activation
      "use_batch_norm": true
    },
    {
      "learning_rate": 0.0008,
      "batch_size": 28,
      "optimizer": "sgd",        # Exploration of different approach
      "activation": "relu",
      "use_batch_norm": false    # Diversity in normalization
    }
  ],
  "insights": [
    "Adam optimizer dominates successful configs (appears in 70% of top results)",
    "ReLU activation consistently outperforms alternatives",
    "Batch normalization correlates with +3% average improvement"
  ]
}
```

### Mixed Numeric and Categorical Constraints

You can freely mix numeric and categorical constraints:

```json
{
  "constraints": {
    "learning_rate": {"min": 0.0001, "max": 0.1, "default": 0.001},
    "batch_size": {"min": 16, "max": 256},
    "dropout": {"min": 0.0, "max": 0.5},
    "optimizer": {"choices": ["adam", "sgd", "rmsprop"]},
    "scheduler": {"choices": ["none", "step", "cosine", "exponential"]},
    "pooling": {"choices": ["max", "avg", "adaptive"]}
  }
}
```

### Tips for Categorical Parameters

1. **Provide enough choices**: Include all reasonable options to explore the space fully
2. **Use historical data**: The more historical results with categorical parameters, the better the suggestions
3. **Combine with numeric**: Categorical and numeric parameters often interact (e.g., optimizer + learning_rate)
4. **Meaningful names**: Use clear, consistent naming across experiments
5. **Case sensitivity**: String choices are case-sensitive ("Adam" ≠ "adam")

## Use Cases

### 1. Building Optimization History

### 1. Building Optimization History

```python
# After each optimization run, inject results
{
  "tool": "hyperparam_inject",
  "arguments": {
    "results": [
      {
        "hyperparameters": {
          "lr": 0.01,
          "bs": 32,
          "optimizer": "adam",
          "activation": "relu"
        },
        "result": 0.92,
        "result_type": "maximize"
      }
    ],
    "experiment_id": "my-experiment"
  }
}
```

### 2. Getting Initial Suggestions

```python
# When starting a new optimization
{
  "tool": "hyperparam_suggest",
  "arguments": {
    "target_params": ["learning_rate", "batch_size", "dropout", "optimizer", "activation"],
    "n_suggestions": 5,
    "constraints": {
      "optimizer": {"choices": ["adam", "sgd", "adamw"]},
      "activation": {"choices": ["relu", "gelu", "tanh"]}
    }
  }
}
```

### 3. Adding New Hyperparameters

```python
# Historical data has 5 params, now want to optimize 6
{
  "tool": "hyperparam_suggest",
  "arguments": {
    "target_params": [
      "learning_rate",
      "batch_size", 
      "dropout",
      "weight_decay",  # New parameter
      "momentum",      # New parameter
      "optimizer"      # New parameter
    ],
    "n_suggestions": 3
  }
}
# Tool will suggest values for all 6 parameters
# New parameters get None or interpolated values
```

## Running the Server

### Standalone

```bash
cd backend/backend_app/hyperparam_advisor_mcp
python server.py
```

### With MCP Watcher

The server is automatically discovered and registered by the MCP watcher daemon.

1. Add to `mcps` table:
```sql
INSERT INTO mcps (name, url, enabled, transport)
VALUES ('hyperparam-advisor', 'stdio:///path/to/server.py', true, 'stdio');
```

2. Watcher will discover tools and add them to `tools` table

3. Tools become available to agents via semantic search

## Integration with RAG

The MCP server integrates with the RAG system:

- **Injection**: Formats hyperparameter results as text documents and stores in RAG via the injector API (HTTP POST to port 5001)
  - Automatically creates RAG group if it doesn't exist
  - Handles duplicates gracefully
  - Supports both private (user-specific) and global (shared) scopes
- **Retrieval**: Queries RAG using vector similarity search to find similar historical optimization runs
  - Filters results by RAG group (`hyperparameter-optimization`)
  - Returns top-k most relevant results
  - Includes similarity scores for ranking
- **User Scoping**: Supports private (user-specific) and global (shared) data

### Environment Variables

- `RAG_INJECTOR_URL`: URL of RAG injector service (default: `http://localhost:5001`)
- `HYPERPARAM_RAG_GROUP`: RAG group name for hyperparameter data (default: `hyperparameter-optimization`)
- `RAG_EMBED_MODEL`: Embedding model to use (default: `nomic-embed-text`)
- `USE_LLM_ANALYSIS`: Enable LLM-based analysis for suggestions (default: `true`)
- `LLM_API_URL`: URL of LLM API endpoint (default: `http://localhost:4000/v1/chat/completions`)

## Suggestion Methods

The tool supports two methods for generating suggestions:

### 1. LLM-Based Analysis (Default)

When `USE_LLM_ANALYSIS=true`, the tool uses a language model to:
- Analyze patterns in historical optimization results
- Identify relationships between hyperparameters
- Generate diverse, intelligent suggestions
- Provide detailed rationale and insights
- Handle new parameters with ML best practices

**Advantages:**
- More sophisticated pattern recognition
- Better handling of complex parameter interactions
- Detailed explanations and insights
- Adaptive to different problem domains

### 2. Heuristic-Based (Fallback)

Falls back to heuristic methods when:
- `USE_LLM_ANALYSIS=false`
- LLM API is unavailable
- LLM analysis fails

**Method:**
- Sorts by performance
- Applies small variations to top configs
- Interpolates between successful configurations
- Simple constraint enforcement

**Advantages:**
- Fast and deterministic
- No external dependencies
- Reliable fallback

## Development

### Requirements

```txt
mcp>=1.0.0
psycopg[binary]>=3.1.0
httpx>=0.27.0
```

Plus LangChain dependencies from parent `rag_common` module for vector search.

### Testing

```bash
# Test inject tool
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"hyperparam_inject","arguments":{"results":[{"hyperparameters":{"lr":0.01},"result":0.9}],"experiment_id":"test"}}}' | python server.py

# Test suggest tool
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hyperparam_suggest","arguments":{"target_params":["learning_rate","batch_size"]}}}' | python server.py
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│          Agent (LangGraph)                      │
│                                                 │
│  "Suggest hyperparameters for                  │
│   learning_rate, batch_size, dropout"          │
└────────────────────┬────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────┐
│     Tools Skill (MCP Client)                    │
│                                                 │
│  Discovers: hyperparam_suggest tool             │
│  Invokes MCP server with arguments              │
└────────────────────┬────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────┐
│   Hyperparameter Advisor MCP Server             │
│                                                 │
│  1. Query RAG for historical results            │
│  2. Parse and analyze patterns                  │
│  3. Generate diverse suggestions                │
│  4. Return with rationale & confidence          │
└────────────────────┬────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────┐
│          RAG System                             │
│                                                 │
│  - Vector store with optimization history       │
│  - Semantic search for similar configurations   │
│  - User-scoped and global data                  │
└─────────────────────────────────────────────────┘
```

## TODO

- [x] Implement actual RAG injection via HTTP POST to rag_injector
- [x] Implement actual RAG query via vector similarity search
- [x] Add LLM-based analysis for more sophisticated suggestions
- [x] Support for categorical hyperparameters (choices-based constraints)
- [ ] Bayesian optimization hints (acquisition function guidance)
- [ ] Multi-objective optimization (multiple metrics simultaneously)
- [ ] Visualization of hyperparameter space (parameter importance, interaction plots)
