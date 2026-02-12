# Categorical Hyperparameters - Quick Reference

## Basic Usage

### Define Categorical Constraints

```json
{
  "constraints": {
    "optimizer": {"choices": ["adam", "sgd", "rmsprop", "adamw"]},
    "activation": {"choices": ["relu", "tanh", "sigmoid", "gelu"]}
  }
}
```

### Mixed with Numeric Constraints

```json
{
  "constraints": {
    "learning_rate": {"min": 0.0001, "max": 0.1},
    "batch_size": {"min": 16, "max": 256},
    "optimizer": {"choices": ["adam", "sgd", "rmsprop"]},
    "activation": {"choices": ["relu", "gelu", "tanh"]}
  }
}
```

## Supported Value Types

- **Strings**: `["adam", "sgd", "rmsprop"]`
- **Booleans**: `[true, false]`
- **Integers**: `[1, 2, 3, 4]`
- **Mixed types**: Not recommended, keep consistent

## How It Works

### LLM-Based (Default)
1. Analyzes frequency in top historical results
2. Considers parameter relationships
3. Selects based on performance patterns
4. Validates against allowed choices
5. Provides insights about effectiveness

### Heuristic-Based (Fallback)
1. Counts frequency in top 10 results
2. Prioritizes most common choices
3. Rotates through options for diversity
4. Uses first choice for new parameters

## Common Patterns

### Deep Learning
```json
{
  "optimizer": {"choices": ["adam", "sgd", "adamw"]},
  "activation": {"choices": ["relu", "gelu", "swish"]},
  "loss": {"choices": ["cross_entropy", "focal"]},
  "scheduler": {"choices": ["none", "step", "cosine"]}
}
```

### Boolean Flags
```json
{
  "use_dropout": {"choices": [true, false]},
  "use_batch_norm": {"choices": [true, false]},
  "use_data_augmentation": {"choices": [true, false]}
}
```

### Architecture Selection
```json
{
  "model": {"choices": ["cnn", "rnn", "lstm", "transformer"]},
  "pooling": {"choices": ["max", "avg", "adaptive"]},
  "normalization": {"choices": ["batch", "layer", "instance", "none"]}
}
```

## Tips

1. **Include all valid options** - Don't limit choices unnecessarily
2. **Use consistent naming** - "adam" vs "Adam" are different
3. **Provide historical data** - More data = better suggestions
4. **Combine with numeric** - Categorical and numeric often interact
5. **Use meaningful names** - Clear parameter names help LLM analysis

## Example Request

```json
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
      "optimizer": {"choices": ["adam", "sgd", "adamw"]},
      "activation": {"choices": ["relu", "gelu", "tanh"]},
      "use_batch_norm": {"choices": [true, false]}
    }
  }
}
```

## Example Response

```json
{
  "suggestions": [
    {
      "learning_rate": 0.001,
      "batch_size": 32,
      "optimizer": "adam",
      "activation": "relu",
      "use_batch_norm": true
    },
    {
      "learning_rate": 0.0015,
      "batch_size": 48,
      "optimizer": "adamw",
      "activation": "gelu",
      "use_batch_norm": true
    },
    {
      "learning_rate": 0.0008,
      "batch_size": 28,
      "optimizer": "sgd",
      "activation": "relu",
      "use_batch_norm": false
    }
  ],
  "insights": [
    "Adam optimizer appears in 70% of top results",
    "ReLU activation consistently outperforms alternatives",
    "Batch normalization correlates with +3% improvement"
  ],
  "confidence": 0.85,
  "method": "llm"
}
```

## Validation

All suggestions are automatically validated:
- Categorical values checked against allowed choices
- Case-insensitive matching for strings
- Invalid values replaced with first valid choice
- Warnings logged for corrections

## Error Handling

If LLM suggests invalid choice:
1. Try case-insensitive match
2. If no match, use first valid choice
3. Log warning with details
4. Continue with corrected value

## Backward Compatibility

Old constraints (numeric only) still work:
```json
{"learning_rate": {"min": 0.001, "max": 0.1}}
```

No breaking changes!
