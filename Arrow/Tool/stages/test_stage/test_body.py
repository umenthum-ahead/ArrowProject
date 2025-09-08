from typing import Optional
from collections import defaultdict
from Arrow.Utils.logger_management import get_logger
from Arrow.Utils.configuration_management import Configuration
from Arrow.Tool.state_management import get_state_manager, get_current_state
from Arrow.Tool.state_management.switch_state import SwitchState
from Arrow.Tool.scenario_management import ScenarioWrapper, get_scenario_manager
from Arrow.Tool.asm_libraries.asm_logger import AsmLogger
from Arrow.Utils.APIs import choice
from Arrow.Tool.asm_libraries.branch_to_segment import branch_to_segment
from Arrow.Utils.statistics_managment import get_statistics_manager
from Arrow.Tool.privilege_management.privilege_manager import get_privilege_manager
from Arrow.Utils.configuration_management.enums import PrivilegeLevel
from Arrow.Tool.asm_libraries.end_test import end_test_asm_convention 


def execute_scenario(scenario_instance):
    # Ensure current_code_block is set before any AsmLogger calls
    current_state = get_current_state()
    if current_state.current_code_block is None:
        logger = get_logger()
        logger.warning(f"current_code_block is None in execute_scenario, AsmLogger calls may fail")
    
    # Only use AsmLogger when paging is enabled
    if Configuration.Knobs.Memory.paging_enabled.get_value():
        AsmLogger.comment(f"========================== Start scenario {scenario_instance} ====================")

    # Check if we got a ScenarioWrapper instance
    if not isinstance(scenario_instance, ScenarioWrapper):
        raise ValueError("Error: Expected a ScenarioWrapper instance but got:", type(scenario_instance))

    statistics_manager = get_statistics_manager()
    statistics_manager.increment("scenario_count")

    current_state = get_current_state()
    pre_scenario_reserved_registers = current_state.register_manager.get_used_registers()

    scenario_instance.func()  # Call the wrapped function

    post_scenario_reserved_registers = current_state.register_manager.get_used_registers()
        
    if pre_scenario_reserved_registers != post_scenario_reserved_registers:
        # find the difference between the two lists
        pre_set = set(pre_scenario_reserved_registers)
        post_set = set(post_scenario_reserved_registers)
        # Changed to post_set - pre_set to find registers that were added but not freed
        difference = post_set - pre_set
                
        raise ValueError(f"Error: Scenario {scenario_instance} has reserved registers that were not freed: {[str(reg) for reg in difference]}")


    # Only use AsmLogger when paging is enabled
    if Configuration.Knobs.Memory.paging_enabled.get_value():
        AsmLogger.comment(f"========================== End scenario {scenario_instance} ====================")

def do_scenario(current_scenario: Optional[int], max_scenario:Optional[int]):
    logger = get_logger()
    state_manager = get_state_manager()
    current_state = state_manager.get_active_state()
    scenario_manager = get_scenario_manager()

    # Handle different state types for page table access
    current_page_table = None
    if hasattr(current_state, 'current_el_page_table') and current_state.current_el_page_table:
        current_page_table = current_state.current_el_page_table
    elif current_state.enabled_page_tables:
        current_page_table = current_state.enabled_page_tables[0]

    if current_page_table:
        available_blocks = current_page_table.segment_manager.get_segments(pool_type=Configuration.Memory_types.CODE, non_exclusive_only=True)
        # Filter the list to exclude the current code block
        available_blocks_without_current = [block for block in available_blocks if block != current_state.current_code_block]
        # Randomly select from the filtered list
        selected_block = choice.choice(values=available_blocks_without_current)
    else:
        # No page table available, scenario execution may be limited
        available_blocks_without_current = []
        selected_block = None

    selected_scenario = scenario_manager.get_random_scenario(tags=dict(Configuration.Knobs.Template.scenario_query.get_value()), current_privilege_level=current_state.privilege_level)

    info_str = f"BODY:: Running {current_state.state_name}, scenario {current_scenario}(:{max_scenario}), scenario {selected_scenario} (privilege level {current_state.privilege_level})"
    logger.info(info_str)
    
    # Only use AsmLogger when paging is enabled
    if Configuration.Knobs.Memory.paging_enabled.get_value():
        AsmLogger.comment(info_str)

    if Configuration.Knobs.Config.privilege_mode_managed.get_value():
        if Configuration.Knobs.Memory.paging_enabled.get_value():
            AsmLogger.asm(f"{selected_scenario.label}:")
        execute_scenario(selected_scenario)
        if Configuration.Architecture.riscv and Configuration.Knobs.Memory.paging_enabled.get_value():
            AsmLogger.asm(f"li {Configuration.RiscvConfig.ecall_arg_reg}, {Configuration.RiscvConfig.ecall_arg_magic_val}")
            AsmLogger.asm("ecall")
        elif not Configuration.Architecture.riscv:
            raise ValueError("managed privilege mode is not supported in non-RISC-V architectures, please remove the 'privilege_mode_managed' knob from the configuration.")
        scenario_manager.register_scenario_for_privilege_level(current_state.privilege_level, selected_scenario)
    else:
        # Only do branching operations when paging is enabled and we have blocks available
        if selected_block is not None and Configuration.Knobs.Memory.paging_enabled.get_value():
            # Is this a pseudo RNG to either do a one-way or two-way branch?
            # If so... why? If ythere is no memory requirement that forces us to do this
            # I don't see the point of this. We are not having memory consistency between scenarios
            two_way_branch = choice.choice(values=[True, False])
            if two_way_branch:
                with branch_to_segment.BranchToSegment(selected_block):
                    execute_scenario(selected_scenario)
            else:
                branch_to_segment.BranchToSegment(selected_block).one_way_branch()
                execute_scenario(selected_scenario)
        else:
            # No paging or no blocks available - execute scenario without branching
            execute_scenario(selected_scenario)

def do_body():
    logger = get_logger()
    state_manager = get_state_manager()
    available_states = state_manager.states_dict
    logger.info("============ do_body")

    # Create per_state_scenario_count as a dictionary: {state_id: (current, max)}
    # Also build privilege_groups during the same loop for efficiency
    per_state_scenario_count = {}
    privilege_groups = defaultdict(list)
    
    privilege_manager = None
    for state_id in available_states:

        with SwitchState(state_id):
            current_state = get_current_state()
            
            # Only use AsmLogger when paging is enabled
            if Configuration.Knobs.Memory.paging_enabled.get_value():
                # Ensure current_code_block is set before any AsmLogger calls
                if current_state.current_code_block is None:
                    # Get a code block to use for logging
                    if hasattr(current_state, 'current_el_page_table') and current_state.current_el_page_table:
                        current_page_table = current_state.current_el_page_table
                    elif current_state.enabled_page_tables:
                        current_page_table = current_state.enabled_page_tables[0]
                    else:
                        logger.warning(f"No page tables available for state {state_id}, AsmLogger calls may fail")
                        current_page_table = None
                    
                    if current_page_table:
                        available_blocks = current_page_table.segment_manager.get_segments(pool_type=Configuration.Memory_types.CODE, non_exclusive_only=True)
                        if available_blocks:
                            from Arrow.Tool.state_management.switch_state import switch_code
                            selected_block = choice.choice(values=available_blocks)
                            switch_code(selected_block)
                        else:
                            logger.warning(f"No code blocks available for state {state_id}, AsmLogger calls may fail")
                
                AsmLogger.comment(f"========================= state {state_id} - TEST BODY - start =====================")
            else:
                # Paging is disabled - set up basic code segment for instruction collection
                logger.debug(f"Paging disabled - setting up non-paging code segment for state {state_id}")
                
                # Ensure current_code_block is set for non-paging mode
                if current_state.current_code_block is None:
                    # The state should already have a NonPagingSegmentManager from initialization
                    # Create a basic code segment for storing generated instructions
                    segment_manager = getattr(current_state, 'segment_manager', None)
                    if segment_manager is None:
                        # Create a NonPagingSegmentManager if one doesn't exist
                        from Arrow.Tool.memory_management.memlayout.non_paging_segment_manager import NonPagingSegmentManager
                        segment_manager = NonPagingSegmentManager(name=f"{state_id}_segments")
                        current_state.segment_manager = segment_manager
                    
                    # Allocate a code segment for this state
                    code_segment = segment_manager.allocate_memory_segment(
                        name=f"{state_id}_main_code", 
                        byte_size=0x100000,  # 1MB should be plenty for generated instructions
                        memory_type=Configuration.Memory_types.CODE,
                        alignment_bits=12  # 4KB alignment
                    )
                    current_state.current_code_block = code_segment
                    logger.debug(f"Created non-paging code segment {code_segment.name} for state {state_id}")
                
                # Add a comment to mark the start of test body (without AsmLogger dependency)
                from Arrow.Tool.asm_blocks import AsmUnit
                comment_unit = AsmUnit(comment=f"========================= state {state_id} - TEST BODY - start =====================")
                current_state.current_code_block.asm_units_list.append(comment_unit)
            privilege_level = current_state.privilege_level
        
            per_state_scenario_count[state_id] = (1, int(Configuration.Knobs.Template.scenario_count)) # TODO:: replace this with per state knob state_manager.scenario_count

            # Group states by privilege level
            privilege_groups[privilege_level].append(state_id)

            if current_state.privilege_level == PrivilegeLevel.RISCV.MACHINE and Configuration.Knobs.Config.privilege_mode_managed.get_value():
                privilege_manager = get_privilege_manager()
                AsmLogger.asm(f"j {privilege_manager.managed_test_body_label}")

    # Sort privilege levels (lowest first) and process each privilege level completely before moving to next
    sorted_privilege_levels = sorted(privilege_groups.keys())
    
    for privilege_level in sorted_privilege_levels:
        available_states_for_privilege = privilege_groups[privilege_level][:]  # Create a copy
        
        while available_states_for_privilege:
            # go over each state in this privilege level, execute scenarios as long as there is what to execute
            # once a certain state reaches its max scenario count, it will be removed from the list
            
            # Iterate over a copy of the list to avoid modifying the list during iteration
            for state_id in available_states_for_privilege[:]:  # Create a shallow copy of the list
                with SwitchState(state_id):
                    current_scenario, max_scenario = per_state_scenario_count[state_id]
                    per_state_scenario_count[state_id] = (current_scenario + 1, max_scenario)
                    if current_scenario == max_scenario:
                        available_states_for_privilege.remove(state_id)
                    do_scenario(current_scenario, max_scenario)

    for state in list(available_states.keys()):
        with SwitchState(state):
            current_state = state_manager.get_active_state()
            logger.info(f"privilege: {current_state.privilege_level} privilege_manager: {privilege_manager}")
            if current_state.privilege_level == PrivilegeLevel.RISCV.MACHINE and privilege_manager:
                logger = get_logger()
                logger.info(f"Generating trap handler and privilege setup for M-mode state {object.__repr__(current_state)} code block {object.__repr__(current_state.current_code_block)}")
                scenario_manager = get_scenario_manager()
                privilege_manager.gen_trap_handler(current_state.privilege_level)
                privilege_manager.gen_privilege_setup()
                # for each m-mode scenario that isn't called by another m-mode scenario (at least one because we guarantee no cycles) call the scenario via mret
                for scenario in scenario_manager.get_unvisited_scenarios_for_privilege_level(PrivilegeLevel.RISCV.MACHINE):
                    privilege_manager.xret_to_scenario(scenario)
                end_test_asm_convention(test_pass=True)
            elif current_state.privilege_level == PrivilegeLevel.RISCV.SUPERVISOR and privilege_manager:
                logger.info("Generating trap handler for S-mode")
                privilege_manager.gen_trap_handler(current_state.privilege_level)
            AsmLogger.comment(f"========================= state_id {state} - privilege {current_state.privilege_level} - TEST BODY - end =====================")
