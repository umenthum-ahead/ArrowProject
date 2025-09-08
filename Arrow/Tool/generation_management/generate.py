import os
import random
from typing import Optional, Any, List, Dict
from Arrow.Tool.generation_management.utils import get_operand_type
from Arrow.Tool.generation_management.generated_instruction import GeneratedInstruction
from Arrow.Tool.generation_management.generate_x86 import generate_x86
from Arrow.Tool.generation_management.generate_riscv import generate_riscv
#from Arrow.Tool.generation_management.generate_arm import old_generate_arm
from Arrow.Tool.generation_management.generate_arm_asl import generate_arm_asl
from Arrow.Utils.configuration_management import Configuration, get_config_manager
from Arrow.Externals.db_manager.models import get_instruction_db
from Arrow.Tool.register_management.register import Register
from Arrow.Tool.memory_management.memory_operand import Memory

from peewee import Expression, fn, SQL


# @staticmethod
def generate(
        instruction_count: Optional[int] = 1,
        query: Optional[Expression | Dict] = None,
        src: Any = None,
        dest: Any = None,
        comment: Optional[str] = None,
        require_random: bool = True,
) -> List[GeneratedInstruction]:
    """
    Generates an instruction with the given mnemonic and operands.

    Parameters:
    - instruction_count (int) : number of instructions to generate.
    - query (Optional[Expression|Dict]) : Peewee query from instructions.db
    - mnemonic (str): The mnemonic of the instruction.
    - src,dest: optional operands for the instruction.
    - comment (str): postfix comment.
    - require_random (bool): whether to filter for random_generate instructions.

    Returns:
    - Instruction: The generated instruction.
    """

    config_manager = get_config_manager()
    instruction_debug_prints = config_manager.get_value('Instruction_debug_prints')
    if instruction_debug_prints:
        print(f"--------------------- generate -------------------------")

    # Get optimized database connection (handles ARM ASL case automatically)
    db_models = get_instruction_db()
    
    if isinstance(db_models, dict):
        # ARM ASL case - returns dict with Instruction and Operand
        Instruction = db_models['Instruction']
        Operand = db_models['Operand']
    else:
        # Standard case - returns Instruction model only
        Instruction = db_models
        Operand = None

    # Start with a base query for instructions
    query_filter = Instruction.select()

    # # Print all instructions
    # query_filter = query_filter[20:30]
    # for instr in list(query_filter):
    #     print(f"   Instruction: {instr.syntax}")
    #     # Sort the operands list by index
    #     sorted_operands = sorted(instr.operands, key=lambda op: op.index)
    #     for op in sorted_operands:
    #         if op.index != -1:
    #             print(f"     Operand{op.index}: text: {op.text}, Category: {op.type_category}, Index: {op.index}, Type: {op.type}, Role: {op.role}, Size: {op.size}, Width: {op.width} ")
    #         else:
    #             print(f"     attribute: text: {op.text}, Category: {op.type_category}, Type: {op.type}, Role: {op.role}, Size: {op.size}, Width: {op.width} ")
    # exit()

    # Filter out all random_generate=False instructions
    if require_random:
        query_filter = query_filter.where(Instruction.random_generate == True)

    # If query is an existing Expression or dict, add it to the query_filter
    if query:
        if isinstance(query, Expression):
            # If query is a single expression, apply it directly
            query_filter = query_filter.where(query)
        elif isinstance(query, dict):
            # If query is a dictionary, construct conditions from key-value pairs
            for key, value in query.items():
                if hasattr(Instruction, key):
                    query_filter = query_filter.where(getattr(Instruction, key) == value)
        else:
            raise ValueError("Invalid query format. Expected Expression or dict.")

    # Apply basic SQL filters first (for ARM ASL case)
    if src is not None:
        query_filter = add_operand_filter(query_filter, src, role="src", Instruction=Instruction, Operand=Operand)
    if dest is not None:
        query_filter = add_operand_filter(query_filter, dest, role="dest", Instruction=Instruction, Operand=Operand)

    # Get all instructions from database and filter in Python for operand matching
    # This avoids SQL JSON binding issues
    all_instructions = list(query_filter)
    
    # Filter instructions based on src/dest operand requirements using Python
    filtered_instructions = []
    debug_info = False  # Disable debug output now that issues are resolved
    
    if debug_info:
        print(f"DEBUG: Filtering {len(all_instructions)} instructions")
        if src: print(f"DEBUG: src operand: {src}, type: {type(src)}, operand.type: {getattr(src, 'type', 'N/A')}")
        if dest: print(f"DEBUG: dest operand: {dest}, type: {type(dest)}, operand.type: {getattr(dest, 'type', 'N/A')}")
    
    for instr in all_instructions:
        import ast
        
        # Parse operands if they're stored as string
        operands_list = instr.operands
        if isinstance(instr.operands, str):
            try:
                operands_list = ast.literal_eval(instr.operands)
            except:
                continue
        
        # Check if instruction matches operand requirements
        src_match = src is None or matches_operand_requirement(operands_list, src, "src")
        dest_match = dest is None or matches_operand_requirement(operands_list, dest, "dest")
        
        if src_match and dest_match:
            filtered_instructions.append(instr)
    
    if debug_info and len(filtered_instructions) == 0:
        print(f"DEBUG: Found {len(filtered_instructions)} matching instructions after filtering")
        # Show sample operand types for debugging
        print("DEBUG: Sample operand types from database:")
        for i, instr in enumerate(all_instructions[:5]):
            operands_list = instr.operands
            if isinstance(instr.operands, str):
                try:
                    operands_list = ast.literal_eval(instr.operands)
                except:
                    continue
            print(f"  Instruction {instr.mnemonic}: {operands_list}")
        
    elif debug_info:
        print(f"DEBUG: Found {len(filtered_instructions)} matching instructions after filtering")
    
    if len(filtered_instructions) == 0:
        raise ValueError("No instructions found matching the specified criteria.")

    instruction_list = []
    for _ in range(instruction_count):
        # Try to find a valid instruction from filtered results
        selected_instruction = None
        for attempt in range(15):
            candidate_instruction = random.choice(filtered_instructions)
            
            # For non-ARM architectures, use random_generate field or skip validation
            if hasattr(candidate_instruction, 'is_valid'):
                # ARM ASL case
                if candidate_instruction.is_valid:
                    selected_instruction = candidate_instruction
                    break
                elif instruction_debug_prints:
                    print(f"        ⚠️   Skipping instruction!!! instruction {candidate_instruction.syntax} is not parsed correctly yet.")
            elif hasattr(candidate_instruction, 'random_generate'):
                # For other architectures, use random_generate or just accept the instruction
                if candidate_instruction.random_generate:
                    selected_instruction = candidate_instruction
                    break
                elif instruction_debug_prints:
                    print(f"        ⚠️   Skipping instruction!!! instruction {candidate_instruction.syntax} is not marked for random generation.")
            else:
                # No validation field available, just use the instruction
                selected_instruction = candidate_instruction
                break
       
        if not selected_instruction:
            raise ValueError("No valid instructions found matching the specified criteria after multiple attempts.")

        # Generate the instruction based on architecture
        if Configuration.Architecture.x86:
            gen_instructions = generate_x86(selected_instruction, src, dest, comment=comment)
        elif Configuration.Architecture.riscv:
            gen_instructions = generate_riscv(selected_instruction, src, dest, comment=comment)
        elif Configuration.Architecture.arm:
            gen_instructions = generate_arm_asl(selected_instruction, src, dest, comment=comment)
        else:
            raise ValueError(f"Unknown Architecture requested")

        instruction_list.extend(gen_instructions)

    return instruction_list


def add_operand_filter(query_filter, operand, role, Instruction, Operand):
    """Add operand-based filters to the query using provided Instruction and Operand models
    
    Updated to work with the new JSON operands format where operands are stored as:
    [{"name": "dest_reg", "type": "reg", "role": "dest", "size": "full_register_width"}, ...]
    """

    config_manager = get_config_manager()
    instruction_debug_prints = config_manager.get_value('Instruction_debug_prints')

    if isinstance(operand, Register):
        if instruction_debug_prints:
            print(f"   Input parameter:: {operand}, role = {role}, type = {operand.type}")

        if operand.type == "sve_pred" and (int(operand.name[1:]) >= 8):
            # ARM SVE predicate specific handling - use Operand join for ARM ASL case
            if Operand is None:
                raise ValueError("Operand model not available for sve_pred filtering")
                
            query_filter = query_filter.join(Operand).where(
                (Operand.role == role) &
                (Operand.type == "sve_pred") &
                (Operand.width == 4) &
                (Operand.is_memory == False)
            )
        # For other register types, skip SQL filtering and do Python filtering later
        # This avoids SQL JSON binding issues

    elif isinstance(operand, Memory):
        if instruction_debug_prints:
            print(f"   Input parameter:: {operand}, role = {role}, type = {type(operand)}")
        # Skip SQL filtering for memory operands too, do Python filtering later

    return query_filter


def matches_operand_requirement(operands_list, operand, role):
    """Check if any operand in the operands_list matches the requirements"""
    if not isinstance(operands_list, list):
        return False
        
    for op in operands_list:
        if not isinstance(op, dict):
            continue
            
        # Check role match
        if op.get('role') != role:
            continue
            
        # Check type match based on operand type
        op_type = op.get('type', '')
        
        if isinstance(operand, Register):
            if operand.type == "gpr":
                # GPR registers match database 'reg' type
                if op_type == 'reg':
                    return True
            elif operand.type == "simdfp":
                # SIMD/FP registers - may need different matching logic
                if op_type.startswith("simdfp") or op_type == 'reg':
                    return True
            else:
                # For exact type matches or other register types
                if op_type == operand.type:
                    return True
        elif isinstance(operand, Memory):
            # For memory operands, look for memory-related types
            if 'mem' in op_type.lower() or op_type == 'offset_plus_basereg':
                return True
    
    return False

