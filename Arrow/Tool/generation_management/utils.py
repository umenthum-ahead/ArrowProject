import random

from Arrow.Utils.configuration_management import Configuration, get_config_manager
from Arrow.Tool.memory_management.memory_operand import Memory
from Arrow.Tool.register_management.register import Register

from Arrow.Tool.asm_libraries.label import LabelImm

def print_instruction(selected_instruction):
    print(f"Mnemonic: {selected_instruction.mnemonic}, Operands: {selected_instruction.operands}, "
          f"random_generate: {selected_instruction.random_generate}, architecture_modes: {selected_instruction.architecture_modes}, "
          f"Type: {selected_instruction.type_}, Group: {selected_instruction.group}, "
          f"Description: {selected_instruction.description}, Syntax: {selected_instruction.syntax}")

def get_operand_type(operand):
    """
    Maps the given operand to its type
    """
    if isinstance(operand, Memory):
        if Configuration.Architecture.riscv:
            return "offset_plus_basereg"
        else:
            return "mem"
    elif isinstance(operand, Register):
        return "reg"
    elif isinstance(operand, int):
        return "imm"
    elif isinstance(operand, LabelImm):
        return "offset_imm"
    else:
        raise ValueError(f"Invalid operand type {type(operand)}")


def find_possible_locations(operands, role, type):
    """
    Find all valid locations to insert the new operand.
    Updated to handle both old object format and new JSON dict format.
    Returns:
        list of int: List of valid indices where the operand can be placed.
    """
    possible_locations = []
    index = 1   # index start from 1 not 0
    for op in operands:
        # Handle both old object format and new dictionary format
        if isinstance(op, dict):
            # New JSON format - operands are dictionaries
            op_type = op.get('type', '')
            op_role = op.get('role', '')
            op_is_operand = True  # In JSON format, all entries are operands
            op_is_memory = 'mem' in op_type.lower() or op_type == 'offset_plus_basereg'
            op_memory_role = op.get('memory_role', 'base') if op_is_memory else None
        else:
            # Old object format
            op_type = getattr(op, 'type', '')
            op_role = getattr(op, 'role', '')
            op_is_operand = getattr(op, 'is_operand', True)
            op_is_memory = getattr(op, 'is_memory', False)
            op_memory_role = getattr(op, 'memory_role', None)
        
        if not op_is_operand:
            index += 1
            continue

        # Skip invalid matching combinations upfront
        if type == "mem" and not op_is_memory:
            # Skip non-memory operands when looking for memory
            pass
        elif type != "mem" and op_is_memory:
            # Skip memory operands when looking for non-memory types
            pass
        elif type == "mem" and op_is_memory:
            if (op_memory_role == "base"):
                # this initial code will only handle the base, and will try to set offset to zero!
                possible_locations.append(index)
        else:
            # Check for register type matches including prefixes
            type_match = (op_type == type) or \
                        (type == "gpr" and (op_type.startswith("gpr") or op_type == "reg")) or \
                        (type == "simdfp" and (op_type.startswith("simdfp") or op_type == "reg")) or \
                        (type == "pred" and op_type.startswith("pred"))
                        
            # Check for role matches including src_dest cases
            role_match = (op_role == role) or \
                        (op_role == "src_dest" and (role == "src" or role == "dest"))
                        
            if type_match and role_match:
                possible_locations.append(index)

        index += 1
    if not possible_locations:
        raise ValueError(f"Couldn't find possible location that match {role} {type} operand")
    else:
        config_manager = get_config_manager()
        instruction_debug_prints = config_manager.get_value('Instruction_debug_prints')
        if instruction_debug_prints:
            print(f"   find_possible_locations for {role} {type} operand: {possible_locations}")
        return possible_locations


def map_inputs_to_operands(selected_instruction, src, dest):
    '''
    In this section, we map src/dest inputs into relevant operands.
    The Instruction.Query have already filtered irrelevant entries and kept just the possible ones that match the input requirements,
    The below code will place them as part of the instruction generation.
    '''
    src_location = None
    dest_location = None
    if src is not None:
        if isinstance(src, Memory): 
            src.type = "mem"
        if isinstance(src, LabelImm):
            src.type = "offset_imm"
        src_locations = find_possible_locations(selected_instruction.operands, role="src", type=src.type)
        src_location = random.choice(src_locations)
    if dest is not None:
        if isinstance(dest, Memory): 
            dest.type = "mem"
        # Handle LabelImm objects which don't have a type attribute
        #if dest.__class__.__name__ == 'LabelImm':
        #    # For labels/immediates, look for offset_imm or label type operands
        #    dest_locations = find_possible_locations(selected_instruction.operands, role="dest", type="offset_imm")
        #    if not dest_locations:
        #        # If no offset_imm, try label type
        #        dest_locations = find_possible_locations(selected_instruction.operands, role="dest", type="label")
        #    if not dest_locations:
        #        # If still no match, try generic imm type
        #        dest_locations = find_possible_locations(selected_instruction.operands, role="dest", type="imm")
        #else:
        #    dest_locations = find_possible_locations(selected_instruction.operands, role="dest", type=dest.type)
        dest_locations = find_possible_locations(selected_instruction.operands, role="dest", type=dest.type)
        dest_location = random.choice(dest_locations)
    if dest is not None and src is not None:
        # if both src/dest input was provided, need to make sure they dont targeting the same operand
        random.shuffle(dest_locations)
        random.shuffle(src_locations)
        src_location = None
        dest_location = None
        # Assign locations without overlap
        for loc1 in src_locations:
            for loc2 in dest_locations:
                if loc1 != loc2:
                    src_location = loc1
                    dest_location = loc2
                    break
        if src_location is None or dest_location is None:
            raise ValueError(f"no valid non-overlapping locations were found")

    return src_location, dest_location