#!/usr/bin/env python3
"""
MODEL CONFIGURATION
Centralized model selection for the entire Portin pipeline.
Allows users to choose between different Gemini models based on their needs.
"""

import os
import json
from typing import Optional

# Available models with their characteristics
AVAILABLE_MODELS = {
    "1": {
        "id": "gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "description": "Fast and reliable (DEFAULT)",
        "cost": "Low",
        "speed": "Fast",
        "quality": "Very Good"
    },
    "2": {
        "id": "gemini-3-flash-preview",
        "name": "Gemini 3 Flash Preview",
        "description": "Latest preview model, cutting-edge capabilities",
        "cost": "Low",
        "speed": "Fast",
        "quality": "Excellent"
    }
}

# Default model
DEFAULT_MODEL = "gemini-2.5-flash"

# Config file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output', 'model_config.json')


def get_current_model() -> str:
    """Get the currently configured model ID."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('model_id', DEFAULT_MODEL)
    except:
        pass
    return DEFAULT_MODEL


def set_model(model_id: str) -> None:
    """Set the model to use for all operations."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            pass

    config['model_id'] = model_id

    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def ask_model_preference() -> str:
    """Interactive model selection."""
    print("\n" + "═"*60)
    print(" GEMINI MODEL SELECTION")
    print("═"*60)
    print("\nSelect the AI model to use for this session:\n")

    for key, model in AVAILABLE_MODELS.items():
        default_tag = " (DEFAULT)" if model['id'] == DEFAULT_MODEL else ""
        print(f"[{key}] {model['name']}{default_tag}")
        print(f"    {model['description']}")
        print(f"    Cost: {model['cost']} | Speed: {model['speed']} | Quality: {model['quality']}")
        print()

    current = get_current_model()
    current_name = next((m['name'] for m in AVAILABLE_MODELS.values() if m['id'] == current), current)
    print(f"Current model: {current_name}")
    print()

    while True:
        choice = input("Select model [1-2] or press Enter for current: ").strip()

        if choice == "":
            print(f"\n[INFO] Using: {current_name}\n")
            return current

        if choice in AVAILABLE_MODELS:
            model = AVAILABLE_MODELS[choice]
            set_model(model['id'])
            print(f"\n[INFO] Selected: {model['name']}\n")
            return model['id']

        print("[ERROR] Please enter 1 or 2")


def get_model_for_task(task_type: str = "general") -> str:
    """
    Get the appropriate model for a specific task type.
    Can be extended to use different models for different tasks.

    task_type: "extraction", "scoring", "search", "general"
    """
    # For now, use the same model for all tasks
    # Could be extended to use lighter models for simple tasks
    return get_current_model()


# Quick test
if __name__ == "__main__":
    model = ask_model_preference()
    print(f"Selected model: {model}")
