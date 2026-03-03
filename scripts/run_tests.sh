#!/bin/bash
echo "Running pytest with coverage..."
pytest tests/ --cov=utils --cov=components --cov-report=term-missing
