"""
Base Exception Handler Class for Arrow

Provides the base interface and common functionality for exception handling
across different architectures. Architecture-specific implementations should
inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from Arrow.Utils.configuration_management import Configuration
from .exception_types import ExceptionType, PrivilegeMode


class ExceptionHandler(ABC):
    """
    Base class for exception handling in Arrow tests.
    
    This class provides the interface and common functionality for generating
    exception handling code and managing exception testing scenarios.
    """
    
    def __init__(self):
        """Initialize the exception handler."""
        self.supported_exceptions: List[ExceptionType] = []
        self.current_privilege_mode = PrivilegeMode.MACHINE
        self.exception_handlers_generated = False
        
    def validate_architecture_support(self) -> None:
        """
        Validate that exception handling is supported for current architecture.
        
        Raises:
            NotImplementedError: If the current architecture doesn't support exception testing
        """
        if not Configuration.Architecture.riscv:
            raise NotImplementedError(
                f"Exception testing is only supported for RISC-V architecture. "
                f"Current architecture: {Configuration.Architecture.get_current()}"
            )
    
    @abstractmethod
    def generate_trap_handler(self, 
                            exception_types: List[ExceptionType],
                            privilege_mode: PrivilegeMode = PrivilegeMode.MACHINE) -> List[str]:
        """
        Generate trap handler assembly code for specified exception types.
        
        Args:
            exception_types: List of exception types to handle
            privilege_mode: The privilege mode for the trap handler
            
        Returns:
            List of assembly instruction strings
        """
        pass
    
    @abstractmethod
    def generate_exception_trigger(self, 
                                 exception_type: ExceptionType,
                                 **kwargs) -> List[str]:
        """
        Generate code that will trigger a specific exception.
        
        Args:
            exception_type: The type of exception to trigger
            **kwargs: Additional parameters specific to the exception type
            
        Returns:
            List of assembly instruction strings that will cause the exception
        """
        pass
    
    @abstractmethod
    def get_recovery_instructions(self, 
                                exception_type: ExceptionType,
                                **kwargs) -> List[str]:
        """
        Generate instructions to recover from an exception.
        
        This typically involves advancing the EPC past the faulting instruction
        and any other necessary cleanup.
        
        Args:
            exception_type: The type of exception to recover from
            **kwargs: Additional parameters for recovery
            
        Returns:
            List of assembly instruction strings for recovery
        """
        pass
    
    def is_exception_supported(self, exception_type: ExceptionType) -> bool:
        """
        Check if a specific exception type is supported.
        
        Args:
            exception_type: The exception type to check
            
        Returns:
            True if the exception type is supported
        """
        return exception_type in self.supported_exceptions
    
    def get_supported_exceptions(self) -> List[ExceptionType]:
        """
        Get the list of supported exception types.
        
        Returns:
            List of supported exception types
        """
        return self.supported_exceptions.copy()
    
    def set_privilege_mode(self, mode: PrivilegeMode) -> None:
        """
        Set the current privilege mode for exception handling.
        
        Args:
            mode: The privilege mode to set
        """
        self.current_privilege_mode = mode
    
    def get_privilege_mode(self) -> PrivilegeMode:
        """
        Get the current privilege mode.
        
        Returns:
            The current privilege mode
        """
        return self.current_privilege_mode
    
    def generate_exception_test_sequence(self,
                                       exception_type: ExceptionType,
                                       num_triggers: int = 1,
                                       **kwargs) -> List[str]:
        """
        Generate a complete test sequence for an exception type.
        
        This includes the trap handler setup, exception trigger, and recovery.
        
        Args:
            exception_type: The type of exception to test
            num_triggers: Number of times to trigger the exception
            **kwargs: Additional parameters for the test sequence
            
        Returns:
            List of assembly instruction strings for the complete test
        """
        if not self.is_exception_supported(exception_type):
            raise ValueError(f"Exception type {exception_type} is not supported")
        
        instructions = []
        
        # Generate trap handler if not already generated
        if not self.exception_handlers_generated:
            instructions.extend(self.generate_trap_handler([exception_type]))
            self.exception_handlers_generated = True
        
        # Generate the exception triggers
        for i in range(num_triggers):
            instructions.append(f"# Exception trigger {i+1}")
            instructions.extend(self.generate_exception_trigger(exception_type, **kwargs))
        
        return instructions
    
    def get_configuration_requirements(self) -> Dict[str, Any]:
        """
        Get the configuration requirements for exception testing.
        
        Returns:
            Dictionary of configuration requirements
        """
        return {
            'architecture': 'riscv',
            'privilege_modes_required': ['machine'],  # Minimum requirement
            'extensions_required': [],  # Base requirements
            'memory_management': 'bare',  # No paging by default
        }
    
    def validate_configuration(self) -> List[str]:
        """
        Validate the current Arrow configuration for exception testing.
        
        Returns:
            List of configuration errors (empty if valid)
        """
        errors = []
        
        # Check architecture
        if not Configuration.Architecture.riscv:
            errors.append("Exception testing requires RISC-V architecture")
        
        # Additional validation can be added by subclasses
        return errors


class ExceptionTestingError(Exception):
    """Custom exception for exception testing related errors."""
    pass