#!/usr/bin/env python3
"""
Test categorical hyperparameter support
"""

import json
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import generate_suggestions

def test_categorical_basic():
    """Test basic categorical parameter handling"""
    print("\n=== Test 1: Basic Categorical Parameters ===")
    
    historical_results = [
        {
            "hyperparameters": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "optimizer": "adam",
                "activation": "relu"
            },
            "result": 0.95,
            "result_type": "maximize"
        },
        {
            "hyperparameters": {
                "learning_rate": 0.01,
                "batch_size": 64,
                "optimizer": "sgd",
                "activation": "tanh"
            },
            "result": 0.89,
            "result_type": "maximize"
        },
        {
            "hyperparameters": {
                "learning_rate": 0.001,
                "batch_size": 48,
                "optimizer": "adam",
                "activation": "relu"
            },
            "result": 0.93,
            "result_type": "maximize"
        }
    ]
    
    constraints = {
        "learning_rate": {"min": 0.0001, "max": 0.1},
        "batch_size": {"min": 16, "max": 128},
        "optimizer": {"choices": ["adam", "sgd", "rmsprop", "adamw"]},
        "activation": {"choices": ["relu", "tanh", "sigmoid", "gelu"]}
    }
    
    result = generate_suggestions(
        historical_results=historical_results,
        target_params=["learning_rate", "batch_size", "optimizer", "activation"],
        result_type="maximize",
        n_suggestions=3,
        constraints=constraints
    )
    
    print(f"Generated {len(result['suggestions'])} suggestions:")
    for i, suggestion in enumerate(result["suggestions"], 1):
        print(f"\n{i}. {json.dumps(suggestion, indent=2)}")
        
        # Validate categorical constraints
        assert suggestion["optimizer"] in constraints["optimizer"]["choices"], \
            f"Invalid optimizer: {suggestion['optimizer']}"
        assert suggestion["activation"] in constraints["activation"]["choices"], \
            f"Invalid activation: {suggestion['activation']}"
        
        # Validate numeric constraints
        assert constraints["learning_rate"]["min"] <= suggestion["learning_rate"] <= constraints["learning_rate"]["max"], \
            f"Learning rate out of bounds: {suggestion['learning_rate']}"
        assert constraints["batch_size"]["min"] <= suggestion["batch_size"] <= constraints["batch_size"]["max"], \
            f"Batch size out of bounds: {suggestion['batch_size']}"
    
    print("\n✓ All suggestions valid!")


def test_categorical_frequency():
    """Test that categorical frequency analysis works"""
    print("\n=== Test 2: Categorical Frequency Analysis ===")
    
    # Create historical data where "adam" appears most frequently in top results
    historical_results = []
    for i in range(10):
        historical_results.append({
            "hyperparameters": {
                "learning_rate": 0.001,
                "optimizer": "adam" if i < 7 else "sgd",  # Adam appears 7/10 times
                "activation": "relu" if i < 8 else "tanh"  # ReLU appears 8/10 times
            },
            "result": 0.95 - i * 0.01,  # Descending order
            "result_type": "maximize"
        })
    
    constraints = {
        "optimizer": {"choices": ["adam", "sgd", "rmsprop"]},
        "activation": {"choices": ["relu", "tanh", "sigmoid"]}
    }
    
    result = generate_suggestions(
        historical_results=historical_results,
        target_params=["learning_rate", "optimizer", "activation"],
        result_type="maximize",
        n_suggestions=5,
        constraints=constraints
    )
    
    print(f"Generated {len(result['suggestions'])} suggestions:")
    
    # Count categorical choices
    optimizer_counts = {}
    activation_counts = {}
    
    for i, suggestion in enumerate(result["suggestions"], 1):
        print(f"\n{i}. optimizer={suggestion['optimizer']}, activation={suggestion['activation']}")
        
        optimizer_counts[suggestion["optimizer"]] = optimizer_counts.get(suggestion["optimizer"], 0) + 1
        activation_counts[suggestion["activation"]] = activation_counts.get(suggestion["activation"], 0) + 1
    
    print(f"\nOptimizer distribution: {optimizer_counts}")
    print(f"Activation distribution: {activation_counts}")
    
    # Adam should appear more frequently since it's in top results
    assert optimizer_counts.get("adam", 0) >= 2, "Adam should appear frequently"
    assert activation_counts.get("relu", 0) >= 2, "ReLU should appear frequently"
    
    print("\n✓ Frequency analysis working correctly!")


def test_categorical_new_param():
    """Test suggesting categorical parameters not in historical data"""
    print("\n=== Test 3: New Categorical Parameters ===")
    
    historical_results = [
        {
            "hyperparameters": {
                "learning_rate": 0.001,
                "batch_size": 32
            },
            "result": 0.95,
            "result_type": "maximize"
        }
    ]
    
    constraints = {
        "learning_rate": {"min": 0.0001, "max": 0.1},
        "optimizer": {"choices": ["adam", "sgd", "rmsprop"]},
        "activation": {"choices": ["relu", "tanh"]}
    }
    
    result = generate_suggestions(
        historical_results=historical_results,
        target_params=["learning_rate", "optimizer", "activation"],
        result_type="maximize",
        n_suggestions=3,
        constraints=constraints
    )
    
    print(f"Generated {len(result['suggestions'])} suggestions:")
    for i, suggestion in enumerate(result["suggestions"], 1):
        print(f"\n{i}. {json.dumps(suggestion, indent=2)}")
        
        # New parameters should have values from choices
        assert suggestion["optimizer"] in constraints["optimizer"]["choices"], \
            f"Invalid optimizer for new parameter: {suggestion['optimizer']}"
        assert suggestion["activation"] in constraints["activation"]["choices"], \
            f"Invalid activation for new parameter: {suggestion['activation']}"
    
    print("\n✓ New categorical parameters handled correctly!")


def test_mixed_constraints():
    """Test mixed numeric and categorical constraints"""
    print("\n=== Test 4: Mixed Numeric and Categorical Constraints ===")
    
    historical_results = [
        {
            "hyperparameters": {
                "learning_rate": 0.001,
                "batch_size": 32,
                "dropout": 0.2,
                "optimizer": "adam",
                "use_batch_norm": True
            },
            "result": 0.95,
            "result_type": "maximize"
        }
    ]
    
    constraints = {
        "learning_rate": {"min": 0.0001, "max": 0.1},
        "batch_size": {"min": 16, "max": 256},
        "dropout": {"min": 0.0, "max": 0.5},
        "optimizer": {"choices": ["adam", "sgd", "adamw"]},
        "use_batch_norm": {"choices": [True, False]},
        "scheduler": {"choices": ["none", "step", "cosine"]}
    }
    
    result = generate_suggestions(
        historical_results=historical_results,
        target_params=["learning_rate", "batch_size", "dropout", "optimizer", "use_batch_norm", "scheduler"],
        result_type="maximize",
        n_suggestions=3,
        constraints=constraints
    )
    
    print(f"Generated {len(result['suggestions'])} suggestions:")
    for i, suggestion in enumerate(result["suggestions"], 1):
        print(f"\n{i}. {json.dumps(suggestion, indent=2)}")
        
        # Validate all constraints
        assert constraints["learning_rate"]["min"] <= suggestion["learning_rate"] <= constraints["learning_rate"]["max"]
        assert constraints["batch_size"]["min"] <= suggestion["batch_size"] <= constraints["batch_size"]["max"]
        assert constraints["dropout"]["min"] <= suggestion["dropout"] <= constraints["dropout"]["max"]
        assert suggestion["optimizer"] in constraints["optimizer"]["choices"]
        assert suggestion["use_batch_norm"] in constraints["use_batch_norm"]["choices"]
        assert suggestion["scheduler"] in constraints["scheduler"]["choices"]
    
    print("\n✓ Mixed constraints handled correctly!")


def test_boolean_categorical():
    """Test boolean categorical parameters"""
    print("\n=== Test 5: Boolean Categorical Parameters ===")
    
    historical_results = [
        {
            "hyperparameters": {
                "learning_rate": 0.001,
                "use_dropout": True,
                "use_batch_norm": False
            },
            "result": 0.95,
            "result_type": "maximize"
        },
        {
            "hyperparameters": {
                "learning_rate": 0.01,
                "use_dropout": False,
                "use_batch_norm": True
            },
            "result": 0.90,
            "result_type": "maximize"
        }
    ]
    
    constraints = {
        "use_dropout": {"choices": [True, False]},
        "use_batch_norm": {"choices": [True, False]}
    }
    
    result = generate_suggestions(
        historical_results=historical_results,
        target_params=["learning_rate", "use_dropout", "use_batch_norm"],
        result_type="maximize",
        n_suggestions=3,
        constraints=constraints
    )
    
    print(f"Generated {len(result['suggestions'])} suggestions:")
    for i, suggestion in enumerate(result["suggestions"], 1):
        print(f"\n{i}. {json.dumps(suggestion, indent=2)}")
        
        assert isinstance(suggestion["use_dropout"], bool), "use_dropout should be boolean"
        assert isinstance(suggestion["use_batch_norm"], bool), "use_batch_norm should be boolean"
        assert suggestion["use_dropout"] in [True, False]
        assert suggestion["use_batch_norm"] in [True, False]
    
    print("\n✓ Boolean categorical parameters handled correctly!")


if __name__ == "__main__":
    print("Testing Categorical Hyperparameter Support")
    print("=" * 50)
    
    try:
        test_categorical_basic()
        test_categorical_frequency()
        test_categorical_new_param()
        test_mixed_constraints()
        test_boolean_categorical()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
