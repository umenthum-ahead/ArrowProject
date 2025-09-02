"""
Exception Testing Template for Arrow

Comprehensive exception testing template that utilizes all the exception
ingredients and integrates with Arrow's existing privilege management.
This template demonstrates how to test various types of exceptions in RISC-V.

RISC-V Only: This template is specifically designed for RISC-V architecture.
"""

import random
from Arrow.Arrow_API import AR
from Arrow.Arrow_API.resources.memory_manager import MemoryManager_API as MemoryManager
from Arrow.Arrow_API.resources.register_manager import RegisterManager_API as RegisterManager
from Arrow.Utils.configuration_management import Configuration
from Arrow.Utils.configuration_management.enums import PrivilegeLevel
from Arrow.Tool.privilege_management.privilege_manager import get_privilege_manager

# Import exception testing components
from Arrow.Tool.exception_management import (
    ExceptionHandler, RiscVExceptionHandler, TrapHandlerGenerator,
    ExceptionType, CauseCode
)
from Arrow.Internal_content.ingredients.exceptions import (
    IllegalInstructionIngredient, AccessFaultIngredient, 
    AMOFaultIngredient, PrivilegeFaultIngredient
)

# Validate RISC-V architecture
if not Configuration.Architecture.riscv:
    raise RuntimeError(
        "Exception testing template is only supported for RISC-V architecture. "
        f"Current architecture: {Configuration.Architecture.get_current()}"
    )

# Configure template settings
Configuration.Knobs.Config.core_count.set_value(1)
Configuration.Knobs.Template.scenario_count.set_value(15)
Configuration.Knobs.Template.scenario_query.set_value({
    "exception_comprehensive_scenario": 30,
    "illegal_instruction_scenario": 20,  
    "access_fault_scenario": 20,
    "amo_fault_scenario": 15,
    "privilege_fault_scenario": 10,
    Configuration.Tag.REST: 5
})


@AR.scenario_decorator(
    random=True,
    priority=Configuration.Priority.HIGH,
    tags=[Configuration.Tag.FEATURE_A, Configuration.Tag.SLOW]
)
def exception_comprehensive_scenario():
    """
    Comprehensive exception testing scenario that combines multiple
    exception types with proper trap handler setup.
    """
    AR.comment("=== Comprehensive Exception Testing Scenario ===")
    
    # Initialize exception handler
    exception_handler = RiscVExceptionHandler()
    trap_generator = TrapHandlerGenerator()
    
    # Define exception types to test
    exception_types = [
        ExceptionType.ILLEGAL_INSTRUCTION,
        ExceptionType.INSTRUCTION_ACCESS_FAULT,
        ExceptionType.LOAD_ACCESS_FAULT,
        ExceptionType.STORE_ACCESS_FAULT,
        ExceptionType.BREAKPOINT,
    ]
    
    # Set up enhanced trap handlers
    privilege_modes = [PrivilegeLevel.RISCV.MACHINE, PrivilegeLevel.RISCV.SUPERVISOR]
    trap_generator.generate_enhanced_trap_handlers(privilege_modes, exception_types)
    
    # Get privilege manager for integration
    privilege_manager = get_privilege_manager()
    privilege_manager.gen_privilege_setup()
    
    AR.comment("Starting comprehensive exception testing sequence")
    
    # Test each exception type
    for i, exception_type in enumerate(exception_types):
        AR.comment(f"Testing exception type {i+1}/{len(exception_types)}: {exception_type.value}")
        
        # Generate test sequence for this exception type
        test_sequence = exception_handler.generate_exception_test_sequence(
            exception_type, num_triggers=2
        )
        
        # Execute some regular instructions between exceptions
        AR.generate(instruction_count=5)
        
        # Generate the exception trigger
        trigger_instructions = exception_handler.generate_exception_trigger(exception_type)
        for instr in trigger_instructions:
            AR.asm(instr)
        
        # Add some recovery instructions
        AR.generate(instruction_count=3)
    
    AR.comment("Comprehensive exception testing completed")


@AR.scenario_decorator(
    random=True,
    priority=Configuration.Priority.MEDIUM,
    tags=[Configuration.Tag.FEATURE_A]
)
def illegal_instruction_scenario():
    """Scenario focused on illegal instruction exception testing."""
    AR.comment("=== Illegal Instruction Testing Scenario ===")
    
    # Create illegal instruction ingredient
    illegal_ingredient = IllegalInstructionIngredient(
        count=8,
        enable_compressed=True
    )
    
    # Initialize and run the ingredient
    illegal_ingredient.init()
    
    AR.comment("Generating various types of illegal instructions")
    
    # Execute the illegal instruction generation
    for instruction_batch in illegal_ingredient.body():
        # Add some regular instructions between illegal ones
        AR.generate(instruction_count=2)
    
    # Show what was generated
    AR.comment(f"Generated {illegal_ingredient.get_generated_count()} illegal instructions")
    
    illegal_ingredient.final()


@AR.scenario_decorator(
    random=True,
    priority=Configuration.Priority.MEDIUM,
    tags=[Configuration.Tag.MEMORY, Configuration.Tag.SLOW]
)
def access_fault_scenario():
    """Scenario focused on PMP access fault testing."""
    AR.comment("=== PMP Access Fault Testing Scenario ===")
    
    # Create access fault ingredient with PMP setup
    access_ingredient = AccessFaultIngredient(
        fault_type=None,  # Use random fault type
        fault_count=6,
        setup_pmp=True
    )
    
    access_ingredient.init()
    
    AR.comment("Testing PMP access faults")
    AR.comment(f"Restricted memory: {access_ingredient.get_restricted_memory_info()}")
    
    # Execute access fault tests
    for fault_test in access_ingredient.body():
        # Add some normal memory operations between faults
        mem = MemoryManager.Memory()
        reg = RegisterManager.get_and_reserve()
        AR.generate(src=mem, dest=reg)
        RegisterManager.free(reg)
    
    access_ingredient.final()


@AR.scenario_decorator(
    random=True,
    priority=Configuration.Priority.MEDIUM,
    tags=[Configuration.Tag.MEMORY]
)
def amo_fault_scenario():
    """Scenario focused on atomic operation fault testing."""
    AR.comment("=== Atomic Operation Fault Testing Scenario ===")
    
    # Create AMO fault ingredient
    amo_ingredient = AMOFaultIngredient(
        fault_type=None,  # Use random fault type
        amo_count=5,
        enable_lr_sc=True,
        setup_restricted_memory=True
    )
    
    amo_ingredient.init()
    
    AR.comment("Testing atomic operation faults")
    AR.comment(f"AMO memory regions: {amo_ingredient.get_memory_regions()}")
    AR.comment(f"Supported AMO operations: {', '.join(amo_ingredient.get_supported_operations()[:5])}...")
    
    # Execute AMO fault tests
    for amo_test in amo_ingredient.body():
        # Add some regular atomic operations between fault tests
        AR.generate(instruction_count=2)
    
    amo_ingredient.final()


@AR.scenario_decorator(
    random=True,
    priority=Configuration.Priority.MEDIUM,
    tags=[Configuration.Tag.MODE_SWITCH]
)
def privilege_fault_scenario():
    """Scenario focused on privilege violation testing."""
    AR.comment("=== Privilege Fault Testing Scenario ===")
    
    # Create privilege fault ingredient
    privilege_ingredient = PrivilegeFaultIngredient(
        fault_count=4,
        test_csr_access=True,
        test_privileged_instrs=True
    )
    
    privilege_ingredient.init()
    
    # Show current privilege information
    priv_info = privilege_ingredient.get_current_privilege_info()
    AR.comment(f"Current privilege: {priv_info['current_privilege']}")
    AR.comment(f"Forbidden CSRs: {len(priv_info['forbidden_csrs'])}")
    AR.comment(f"Forbidden instructions: {len(priv_info['forbidden_instructions'])}")
    
    # Execute privilege fault tests
    for priv_test in privilege_ingredient.body():
        # Add some allowed operations between privilege violations
        AR.generate(instruction_count=2)
    
    privilege_ingredient.final()


@AR.scenario_decorator(
    random=False,
    priority=Configuration.Priority.LOW,
    tags=[Configuration.Tag.FAST]
)
def exception_validation_scenario():
    """
    Validation scenario that tests the exception handling infrastructure
    without necessarily triggering exceptions.
    """
    AR.comment("=== Exception Infrastructure Validation ===")
    
    # Test exception handler initialization
    exception_handler = RiscVExceptionHandler()
    
    # Validate configuration
    config_errors = exception_handler.validate_configuration()
    if config_errors:
        AR.comment(f"Configuration errors found: {len(config_errors)}")
        for error in config_errors:
            AR.comment(f"  - {error}")
    else:
        AR.comment("Exception handler configuration valid")
    
    # Test supported exceptions
    supported_exceptions = exception_handler.get_supported_exceptions()
    AR.comment(f"Supported exception types: {len(supported_exceptions)}")
    
    for exc_type in supported_exceptions[:3]:  # Show first few
        AR.comment(f"  - {exc_type.value}")
    
    # Generate some normal instructions to test basic functionality
    AR.comment("Generating normal instruction sequence")
    AR.generate(instruction_count=20)
    
    # Test memory operations
    mem = MemoryManager.Memory(name="validation_memory", init_value=0x12345678)
    reg = RegisterManager.get_and_reserve()
    
    AR.generate(src=mem, dest=reg, comment="Load from validation memory")
    AR.generate(dest=mem, src=reg, comment="Store to validation memory")
    
    RegisterManager.free(reg)
    
    AR.comment("Exception infrastructure validation completed")


@AR.scenario_decorator(
    random=False,
    priority=Configuration.Priority.LOW,
    tags=[Configuration.Tag.FAST]
)
def exception_demo_scenario():
    """
    Demonstration scenario showing how to use exception testing ingredients
    in a controlled manner.
    """
    AR.comment("=== Exception Testing Demonstration ===")
    
    AR.comment("This scenario demonstrates safe exception testing")
    
    # Demonstrate illegal instruction generation (without executing)
    AR.comment("Demonstrating illegal instruction patterns:")
    
    # Generate a few illegal instructions for demonstration
    demo_illegal = IllegalInstructionIngredient(count=2, enable_compressed=False)
    demo_illegal.init()
    
    AR.comment("Illegal instruction examples (as data, not executed):")
    # The ingredient will generate .word directives for illegal instructions
    
    demo_illegal.final()
    
    # Demonstrate normal exception recovery patterns
    AR.comment("Demonstrating normal exception handling patterns:")
    
    # Set up a simple breakpoint for demonstration
    AR.comment("Setting up demonstration breakpoint")
    AR.asm("ebreak  # Demonstration breakpoint - will be handled by trap handler")
    
    # Continue with normal execution
    AR.generate(instruction_count=10)
    
    AR.comment("Exception testing demonstration completed")


# Template execution starts here
# The scenarios will be executed based on the scenario_query configuration