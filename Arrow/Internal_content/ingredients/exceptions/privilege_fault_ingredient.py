"""
Privilege Fault Ingredient for Exception Testing

Generates privilege violations by attempting to execute instructions that are
not allowed in the current privilege mode, causing illegal instruction exceptions.

RISC-V Only: This ingredient is specifically designed for RISC-V architecture.
"""

import random
from typing import List, Optional, Dict, Any, Set
from enum import Enum

from Arrow.Arrow_API import AR
from Arrow.Arrow_API.resources.register_manager import RegisterManager_API as RegisterManager
from Arrow.Arrow_API import AR
from Arrow.Utils.configuration_management import Configuration
from Arrow.Utils.configuration_management.enums import PrivilegeLevel
from Arrow.Tool.exception_management import ExceptionType
from Arrow.Tool.asm_libraries.asm_logger import AsmLogger
from Arrow.Tool.state_management import get_state_manager


class PrivilegedInstruction(Enum):
    """Privileged instructions that can cause faults"""
    MRET = ("mret", PrivilegeLevel.RISCV.MACHINE)
    SRET = ("sret", PrivilegeLevel.RISCV.SUPERVISOR)
    WFI = ("wfi", PrivilegeLevel.RISCV.SUPERVISOR)  # Can be restricted
    SFENCE_VMA = ("sfence.vma", PrivilegeLevel.RISCV.SUPERVISOR)


class PrivilegedCSR(Enum):
    """Privileged CSRs that can cause access faults"""
    # Machine-level CSRs (require M-mode)
    MSTATUS = (0x300, PrivilegeLevel.RISCV.MACHINE)
    MISA = (0x301, PrivilegeLevel.RISCV.MACHINE)
    MEDELEG = (0x302, PrivilegeLevel.RISCV.MACHINE)
    MIDELEG = (0x303, PrivilegeLevel.RISCV.MACHINE)
    MIE = (0x304, PrivilegeLevel.RISCV.MACHINE)
    MTVEC = (0x305, PrivilegeLevel.RISCV.MACHINE)
    MSCRATCH = (0x340, PrivilegeLevel.RISCV.MACHINE)
    MEPC = (0x341, PrivilegeLevel.RISCV.MACHINE)
    MCAUSE = (0x342, PrivilegeLevel.RISCV.MACHINE)
    MTVAL = (0x343, PrivilegeLevel.RISCV.MACHINE)
    MIP = (0x344, PrivilegeLevel.RISCV.MACHINE)
    
    # Supervisor-level CSRs (require S-mode or higher)
    SSTATUS = (0x100, PrivilegeLevel.RISCV.SUPERVISOR)
    SIE = (0x104, PrivilegeLevel.RISCV.SUPERVISOR)
    STVEC = (0x105, PrivilegeLevel.RISCV.SUPERVISOR)
    SSCRATCH = (0x140, PrivilegeLevel.RISCV.SUPERVISOR)
    SEPC = (0x141, PrivilegeLevel.RISCV.SUPERVISOR)
    SCAUSE = (0x142, PrivilegeLevel.RISCV.SUPERVISOR)
    STVAL = (0x143, PrivilegeLevel.RISCV.SUPERVISOR)
    SIP = (0x144, PrivilegeLevel.RISCV.SUPERVISOR)
    SATP = (0x180, PrivilegeLevel.RISCV.SUPERVISOR)
    
    @property
    def address(self) -> int:
        return self.value[0]
    
    @property
    def required_privilege(self) -> PrivilegeLevel:
        return self.value[1]


@AR.ingredient_decorator
class PrivilegeFaultIngredient(AR.Ingredient):
    """
    Ingredient that generates privilege violations by attempting to execute
    privileged instructions or access privileged CSRs from insufficient privilege levels.
    """
    
    def __init__(self,
                 fault_count: int = 5,
                 test_csr_access: bool = True,
                 test_privileged_instrs: bool = True):
        """
        Initialize the privilege fault ingredient.
        
        Args:
            fault_count: Number of privilege violations to generate
            test_csr_access: Whether to test privileged CSR access
            test_privileged_instrs: Whether to test privileged instructions
        """
        # Validate RISC-V architecture
        if not Configuration.Architecture.riscv:
            raise RuntimeError(
                "Privilege fault testing is only supported for RISC-V architecture. "
                f"Current architecture: {Configuration.Architecture.get_current()}"
            )
        
        self.name = "privilege_fault_ingredient"
        self.fault_count = fault_count
        self.test_csr_access = test_csr_access
        self.test_privileged_instrs = test_privileged_instrs
        
        self.test_registers = []
        
    def init(self):
        """Initialize ingredient resources."""
        AR.comment(f"Initializing {self.name}")
        
        # Reserve registers for privilege testing
        self.test_registers = [
            RegisterManager.get_and_reserve() for _ in range(3)
        ]
        
        # Get current privilege level from state manager
        state_manager = get_state_manager()
        current_state = state_manager.get_active_state()
        self.current_privilege = current_state.privilege_level
        
        AR.comment(f"Current privilege level: {self.current_privilege}")
    
    def body(self):
        """Generate privilege fault test sequences."""
        AR.comment(f"Generating {self.fault_count} privilege fault tests")
        
        for i in range(self.fault_count):
            AR.comment(f"Privilege fault test {i+1}")
            
            # Randomly choose between CSR access and privileged instruction faults
            fault_types = []
            if self.test_csr_access:
                fault_types.append("csr_access")
            if self.test_privileged_instrs:
                fault_types.append("privileged_instr")
            
            if not fault_types:
                AR.comment("No privilege fault types enabled")
                continue
            
            fault_type = random.choice(fault_types)
            
            if fault_type == "csr_access":
                self._generate_csr_access_fault()
            else:  # privileged_instr
                self._generate_privileged_instruction_fault()
            
            # Add spacing
            AsmLogger.asm("nop  # Privilege fault test spacing")
            
            yield  # Important: yield for proper state management
    
    def final(self):
        """Clean up ingredient resources."""
        AR.comment(f"Finalizing {self.name}")
        
        # Free reserved registers
        for reg in self.test_registers:
            RegisterManager.free(reg)
        
        self.test_registers.clear()
    
    def _generate_csr_access_fault(self):
        """Generate fault by accessing privileged CSR from insufficient privilege level."""
        AR.comment("Testing privileged CSR access")
        
        # Find CSRs that require higher privilege than current level
        forbidden_csrs = self._get_forbidden_csrs()
        
        if not forbidden_csrs:
            AR.comment("No forbidden CSRs for current privilege level")
            return
        
        # Choose a random forbidden CSR
        csr = random.choice(forbidden_csrs)
        reg = self.test_registers[0]
        
        # Generate CSR access instructions that should fault
        csr_ops = ["csrr", "csrw", "csrs", "csrc"]
        csr_op = random.choice(csr_ops)
        
        AR.comment(f"Attempting {csr_op} on {csr.name} (0x{csr.address:03x}) "
                  f"from {self.current_privilege} - should fault")
        
        if csr_op == "csrr":
            # CSR read
            AsmLogger.asm(f"csrr {reg}, 0x{csr.address:03x}  # Read {csr.name} - will fault")
        elif csr_op == "csrw":
            # CSR write
            AsmLogger.asm(f"li {reg}, 0x12345678")
            AsmLogger.asm(f"csrw 0x{csr.address:03x}, {reg}  # Write {csr.name} - will fault")
        elif csr_op == "csrs":
            # CSR set bits
            AsmLogger.asm(f"li {reg}, 0x1")
            AsmLogger.asm(f"csrs 0x{csr.address:03x}, {reg}  # Set bits in {csr.name} - will fault")
        else:  # csrc
            # CSR clear bits
            AsmLogger.asm(f"li {reg}, 0x1")
            AsmLogger.asm(f"csrc 0x{csr.address:03x}, {reg}  # Clear bits in {csr.name} - will fault")
    
    def _generate_privileged_instruction_fault(self):
        """Generate fault by executing privileged instruction from insufficient privilege level."""
        AR.comment("Testing privileged instruction execution")
        
        # Find instructions that require higher privilege than current level
        forbidden_instrs = self._get_forbidden_instructions()
        
        if not forbidden_instrs:
            AR.comment("No forbidden instructions for current privilege level")
            return
        
        # Choose a random forbidden instruction
        instr = random.choice(forbidden_instrs)
        instr_name, required_priv = instr.value
        
        AR.comment(f"Attempting {instr_name} from {self.current_privilege} "
                  f"(requires {required_priv}) - should fault")
        
        if instr == PrivilegedInstruction.MRET:
            AsmLogger.asm("mret  # Machine return - will fault if not in M-mode")
        elif instr == PrivilegedInstruction.SRET:
            AsmLogger.asm("sret  # Supervisor return - will fault if not in S-mode or higher")
        elif instr == PrivilegedInstruction.WFI:
            AsmLogger.asm("wfi  # Wait for interrupt - may fault based on mstatus.TW")
        elif instr == PrivilegedInstruction.SFENCE_VMA:
            # SFENCE.VMA with random registers
            rs1 = self.test_registers[0]
            rs2 = self.test_registers[1]
            AsmLogger.asm(f"sfence.vma {rs1}, {rs2}  # Supervisor fence - will fault if not in S-mode or higher")
    
    def _get_forbidden_csrs(self) -> List[PrivilegedCSR]:
        """Get list of CSRs that are forbidden for current privilege level."""
        forbidden = []
        
        for csr in PrivilegedCSR:
            if self._is_csr_forbidden(csr):
                forbidden.append(csr)
        
        return forbidden
    
    def _get_forbidden_instructions(self) -> List[PrivilegedInstruction]:
        """Get list of instructions that are forbidden for current privilege level."""
        forbidden = []
        
        for instr in PrivilegedInstruction:
            if self._is_instruction_forbidden(instr):
                forbidden.append(instr)
        
        return forbidden
    
    def _is_csr_forbidden(self, csr: PrivilegedCSR) -> bool:
        """Check if a CSR is forbidden for the current privilege level."""
        return csr.required_privilege > self.current_privilege
    
    def _is_instruction_forbidden(self, instr: PrivilegedInstruction) -> bool:
        """Check if an instruction is forbidden for the current privilege level."""
        _, required_priv = instr.value
        
        # Special handling for WFI - it's more complex
        if instr == PrivilegedInstruction.WFI:
            # WFI can be trapped in S-mode if mstatus.TW is set
            # For testing purposes, assume it might fault in S-mode
            return self.current_privilege < PrivilegeLevel.RISCV.SUPERVISOR
        
        return required_priv > self.current_privilege
    
    def _generate_privilege_escalation_attempt(self):
        """Generate attempt to escalate privilege (always illegal)."""
        AR.comment("Attempting privilege escalation")
        
        reg = self.test_registers[0]
        
        if self.current_privilege == PrivilegeLevel.RISCV.USER:
            # User mode trying to set SSTATUS.SPP or access machine CSRs
            AR.comment("User mode attempting to access supervisor CSRs")
            AsmLogger.asm(f"csrr {reg}, sstatus  # User accessing SSTATUS - will fault")
            
        elif self.current_privilege == PrivilegeLevel.RISCV.SUPERVISOR:
            # Supervisor mode trying to access machine CSRs
            AR.comment("Supervisor mode attempting to access machine CSRs")
            AsmLogger.asm(f"csrr {reg}, mstatus  # Supervisor accessing MSTATUS - will fault")
    
    def _generate_csr_permission_test(self):
        """Test CSR access permissions comprehensively."""
        AR.comment("Comprehensive CSR permission test")
        
        reg = self.test_registers[0]
        
        # Test read-only CSRs with write attempts
        readonly_csrs = {
            0xC00: "cycle",    # Always readable
            0xC01: "time",     # Always readable
            0xC02: "instret",  # Always readable
            0x301: "misa",     # May be read-only
        }
        
        for csr_addr, csr_name in readonly_csrs.items():
            # First try to read (should succeed if accessible)
            AsmLogger.asm(f"csrr {reg}, 0x{csr_addr:03x}  # Read {csr_name}")
            
            # Then try to write (may fault if read-only or inaccessible)
            AsmLogger.asm(f"li {reg}, 1")
            AsmLogger.asm(f"csrw 0x{csr_addr:03x}, {reg}  # Write {csr_name} - may fault")
            
            yield
    
    def get_current_privilege_info(self) -> Dict[str, Any]:
        """Get information about current privilege level and capabilities."""
        return {
            'current_privilege': str(self.current_privilege),
            'forbidden_csrs': [csr.name for csr in self._get_forbidden_csrs()],
            'forbidden_instructions': [instr.name for instr in self._get_forbidden_instructions()],
            'accessible_csrs': [csr.name for csr in PrivilegedCSR if not self._is_csr_forbidden(csr)],
        }
    
    @staticmethod
    def get_privilege_hierarchy() -> List[PrivilegeLevel]:
        """Get the RISC-V privilege level hierarchy."""
        return [
            PrivilegeLevel.RISCV.USER,
            PrivilegeLevel.RISCV.SUPERVISOR,
            PrivilegeLevel.RISCV.MACHINE
        ]
    
    @staticmethod
    def can_access_csr(current_priv: PrivilegeLevel, target_csr: PrivilegedCSR) -> bool:
        """Check if a privilege level can access a specific CSR."""
        return current_priv >= target_csr.required_privilege
    
    @staticmethod
    def can_execute_instruction(current_priv: PrivilegeLevel, 
                               target_instr: PrivilegedInstruction) -> bool:
        """Check if a privilege level can execute a specific instruction."""
        _, required_priv = target_instr.value
        return current_priv >= required_priv