"""
Module to suppress specific warnings that are known and understood.
Import this module at the start of application to filter out specific warnings.
"""

import warnings

# Suppress Pydantic V2 json_encoders deprecation warnings
warnings.filterwarnings(
    "ignore",
    message=r".*`json_encoders` is deprecated.*",
    category=DeprecationWarning
)
