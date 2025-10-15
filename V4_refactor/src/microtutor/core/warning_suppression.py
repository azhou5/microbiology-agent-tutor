"""
Warning Suppression Configuration for MicroTutor V4

This module provides centralized warning suppression for third-party libraries
that generate deprecation warnings and runtime warnings that don't affect
application functionality.

Suppressed warnings:
- RDKit boost::shared_ptr converter warnings
- pkg_resources deprecation warnings
- admet_ai path deprecation warnings
- hyperopt pkg_resources deprecation warnings
"""

import warnings
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class WarningSuppressor:
    """Centralized warning suppression for third-party library warnings."""
    
    # Define warning patterns to suppress
    WARNING_PATTERNS: List[Tuple[str, type, str]] = [
        # RDKit boost::shared_ptr converter warnings
        ("ignore", RuntimeWarning, ".*boost::shared_ptr.*"),
        
        # pkg_resources deprecation warnings
        ("ignore", DeprecationWarning, "module=pkg_resources"),
        ("ignore", DeprecationWarning, ".*pkg_resources.*"),
        
        # admet_ai path deprecation warnings
        ("ignore", DeprecationWarning, "module=admet_ai"),
        ("ignore", DeprecationWarning, ".*path is deprecated.*"),
        
        # hyperopt pkg_resources deprecation warnings
        ("ignore", DeprecationWarning, "module=hyperopt"),
        ("ignore", DeprecationWarning, ".*pkg_resources is deprecated.*"),
        
        # Additional common deprecation warnings
        ("ignore", DeprecationWarning, ".*declare_namespace.*"),
    ]
    
    @classmethod
    def suppress_warnings(cls, verbose: bool = False) -> None:
        """
        Apply all warning suppressions.
        
        Args:
            verbose: If True, log which warnings are being suppressed
        """
        suppressed_count = 0
        
        for action, category, message in cls.WARNING_PATTERNS:
            try:
                if message.startswith("module="):
                    # Module-specific suppression
                    module_name = message.split("=", 1)[1]
                    warnings.filterwarnings(action, category=category, module=module_name)
                else:
                    # Message pattern suppression
                    warnings.filterwarnings(action, category=category, message=message)
                
                suppressed_count += 1
                
                if verbose:
                    logger.debug(f"Suppressed {category} warnings: {message}")
                    
            except Exception as e:
                logger.warning(f"Failed to suppress warning pattern {message}: {e}")
        
        if verbose:
            logger.info(f"Applied {suppressed_count} warning suppressions")
    
    @classmethod
    def suppress_specific_warnings(
        cls, 
        patterns: List[Tuple[str, type, str]], 
        verbose: bool = False
    ) -> None:
        """
        Suppress specific warning patterns.
        
        Args:
            patterns: List of (action, category, message) tuples
            verbose: If True, log which warnings are being suppressed
        """
        for action, category, message in patterns:
            try:
                if message.startswith("module="):
                    module_name = message.split("=", 1)[1]
                    warnings.filterwarnings(action, category=category, module=module_name)
                else:
                    warnings.filterwarnings(action, category=category, message=message)
                
                if verbose:
                    logger.debug(f"Suppressed {category} warnings: {message}")
                    
            except Exception as e:
                logger.warning(f"Failed to suppress warning pattern {message}: {e}")
    
    @classmethod
    def reset_warnings(cls) -> None:
        """Reset all warning filters (useful for testing)."""
        warnings.resetwarnings()
        logger.debug("Warning filters reset")


def setup_warning_suppression(verbose: bool = False) -> None:
    """
    Convenience function to set up warning suppression.
    
    Args:
        verbose: If True, log which warnings are being suppressed
    """
    WarningSuppressor.suppress_warnings(verbose=verbose)


def suppress_rdkit_warnings(verbose: bool = False) -> None:
    """
    Suppress only RDKit-related warnings.
    
    Args:
        verbose: If True, log which warnings are being suppressed
    """
    rdkit_patterns = [
        ("ignore", RuntimeWarning, ".*boost::shared_ptr.*"),
    ]
    WarningSuppressor.suppress_specific_warnings(rdkit_patterns, verbose=verbose)


def suppress_deprecation_warnings(verbose: bool = False) -> None:
    """
    Suppress only deprecation warnings from third-party libraries.
    
    Args:
        verbose: If True, log which warnings are being suppressed
    """
    deprecation_patterns = [
        ("ignore", DeprecationWarning, "module=pkg_resources"),
        ("ignore", DeprecationWarning, ".*pkg_resources.*"),
        ("ignore", DeprecationWarning, "module=admet_ai"),
        ("ignore", DeprecationWarning, ".*path is deprecated.*"),
        ("ignore", DeprecationWarning, "module=hyperopt"),
        ("ignore", DeprecationWarning, ".*pkg_resources is deprecated.*"),
        ("ignore", DeprecationWarning, ".*declare_namespace.*"),
    ]
    WarningSuppressor.suppress_specific_warnings(deprecation_patterns, verbose=verbose)


# Auto-suppress warnings when module is imported
# Only do this if we're not in a test environment to avoid import issues
if __name__ != "__main__":
    try:
        setup_warning_suppression(verbose=False)
    except Exception:
        # If there are any import issues, just skip auto-suppression
        # The warnings will be suppressed when the main app starts
        pass
