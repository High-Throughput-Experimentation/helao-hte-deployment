"""Experiment library for the HISPEC deployment.

Provides sub-experiment builders that assemble action lists for the orchestrator
to drive the HISPEC potentiostat, motor, IO, PAL and Andor camera servers. Each
function returns a list of planned actions built by an `ActionPlanMaker`.
"""

# everything is a 'machine model schema '
EXPERIMENTS = [
    # "HISPEC_analysis_stability",
    "HISPEC_calculate_lower_vertex_potential",
    "HISPEC_sub_add_liquid",
    "HISPEC_sub_CA",
    # "HISPEC_sub_CA_led",
    "HISPEC_sub_cooldown",
    "HISPEC_sub_CP",
    # "HISPEC_sub_CP_led",
    # "HISPEC_sub_CV_DOtrigger",
    "HISPEC_sub_disengage",
    "HISPEC_sub_engage",
    "HISPEC_sub_load_solid",
    "HISPEC_sub_OCV",
    # "HISPEC_sub_OCV_led",
    "HISPEC_sub_PEIS",
    "HISPEC_sub_shutdown",
    "HISPEC_sub_SpEC",
    "HISPEC_sub_startup",
    "HISPEC_sub_stop_flow",
    "HISPEC_sub_unloadall_customs",
]

from helao.deploy.hte.experiments import ECHE_exp, ECHEUVIS_exp
from helao.helpers import helao_logging as logging

if logging.LOGGER is None:
    logger = logging.make_logger(__file__)
else:
    logger = logging.LOGGER

from helao.helpers import config_loader

if config_loader.CONFIG is None:
    rootcfg = {}
else:
    rootcfg = config_loader.CONFIG

from socket import gethostname

from helao.core.models.action_start_condition import ActionStartCondition
from helao.core.models.machine import MachineModel as MM
from helao.core.models.process_contrib import ProcessContrib
from helao.core.models.sample import LiquidSample, SolidSample
from helao.deploy.hte.servers.galil_io.enum import TriggerType
from helao.deploy.hte.servers.galil_motion.enum import MoveModes, TransformationModes
from helao.helpers.lib_decorators import experiment
from helao.helpers.premodels import ActionPlanMaker

# these must all be defined but you may not use any of them in the experiment
PSTAT_server = MM(
    server_name="PSTAT", machine_name=gethostname().lower()
).as_dict()  # get host name as local server
MOTOR_server = MM(server_name="MOTOR", machine_name=gethostname().lower()).as_dict()
IO_server = MM(server_name="IO", machine_name=gethostname().lower()).as_dict()
ANDOR_server = MM(server_name="ANDOR", machine_name=gethostname().lower()).as_dict()
ORCH_server = MM(server_name="ORCH", machine_name=gethostname().lower()).as_dict()
PAL_server = MM(server_name="PAL", machine_name=gethostname().lower()).as_dict()
SAMPLE_server = MM(server_name="SAMPLE", machine_name=gethostname().lower()).as_dict()
# CAM_server = MM(server_name="CAM", machine_name=gethostname().lower()).as_dict()
KMOTOR_server = MM(server_name="KMOTOR", machine_name=gethostname().lower()).as_dict()
# ANA_server = MM(server_name="ANA", machine_name=gethostname().lower()).as_dict()
CALC_server = MM(server_name="CALC", machine_name=gethostname().lower()).as_dict()

toggle_triggertype = TriggerType.risingedge


@experiment(version=1)
def HISPEC_sub_cooldown() -> list:
    """Run the Andor detector cooling action.

    Returns:
        List of planned actions invoking the Andor server `cooling` endpoint.
    """
    apm = ActionPlanMaker()
    apm.add(ANDOR_server, "cooling", {})
    return apm.planned_actions


@experiment(version=1)
def HISPEC_sub_stop_flow() -> list:
    """Switch off the working- and counter-electrode flow/pump digital outputs.

    Returns:
        List of `set_digital_out` actions on the IO server clearing
        ``we_flow``, ``we_pump`` and ``ce_pump``.
    """
    apm = ActionPlanMaker()
    for item, flow_flag in (
        ("we_flow", False),
        ("we_pump", False),
        ("ce_pump", False),
    ):
        apm.add(
            IO_server,
            "set_digital_out",
            {"do_item": item, "on": flow_flag},
            ActionStartCondition.no_wait,
        )
    return apm.planned_actions


@experiment(version=1)
def HISPEC_sub_unloadall_customs() -> list:
    """Alias of :func:`ECHE_sub_unloadall_customs`, published so queued runs resolve."""
    return ECHE_exp.ECHE_sub_unloadall_customs(**locals())


@experiment(version=2)
def HISPEC_sub_add_liquid(
    solid_custom_position: str = "cell1_we",
    reservoir_liquid_sample_no: int = 1,
    solution_bubble_gas: str = "O2",
    liquid_volume_ml: float = 1.0,
) -> list:
    """Alias of :func:`ECHE_sub_add_liquid`, published so queued runs resolve."""
    return ECHE_exp.ECHE_sub_add_liquid(**locals())


@experiment(version=1)
def HISPEC_sub_load_solid(
    solid_custom_position: str = "cell1_we",
    solid_plate_id: int = 4534,
    solid_sample_no: int = 1,
) -> list:
    """Alias of :func:`ECHE_sub_load_solid`, published so queued runs resolve."""
    return ECHE_exp.ECHE_sub_load_solid(**locals())


@experiment(version=1)
def HISPEC_sub_engage(
    flow_we: bool = True,
    flow_ce: bool = True,
    z_height: float = 1.5,
    fill_wait: float = 10.0,
    # calibrate_intensity: bool = False,
    max_integration_time: int = 150,
    # illumination_source: str = "doric_wled",
) -> list:
    """Alias of :func:`ECHEUVIS_sub_engage`, published so queued runs resolve."""
    return ECHEUVIS_exp.ECHEUVIS_sub_engage(**locals())


@experiment(version=1)
def HISPEC_sub_disengage(
    clear_we: bool = True,
    clear_ce: bool = False,
    z_height: float = 0,
    vent_wait: float = 10.0,
) -> list:
    """Alias of :func:`ECHEUVIS_sub_disengage`, published so queued runs resolve."""
    return ECHEUVIS_exp.ECHEUVIS_sub_disengage(**locals())


@experiment(version=2)
def HISPEC_sub_startup(
    solid_custom_position: str = "cell1_we",
    solid_plate_id: int = 4534,
    solid_sample_no: int = 1,
    reservoir_liquid_sample_no: int = 1,
    solution_bubble_gas: str = "N2",
    liquid_volume_ml: float = 1.0,
) -> list:
    """Alias of :func:`ECHE_sub_startup`, published so queued runs resolve."""
    return ECHE_exp.ECHE_sub_startup(**locals())


@experiment(version=1)
def HISPEC_sub_shutdown() -> list:
    """Alias of :func:`ECHE_sub_shutdown`, published so queued runs resolve."""
    return ECHE_exp.ECHE_sub_shutdown(**locals())


@experiment(version=1)
def HISPEC_calculate_lower_vertex_potential(
    min_offset_ocv: float = 3,
    new_ocv: float = 3,
    offset_value: float = -0.2,
) -> list:
    """Track the minimum OCV and compute a lower vertex potential.

    Args:
        min_offset_ocv: Running minimum OCV (with offset already applied).
        new_ocv: Latest OCV measurement to compare against ``min_offset_ocv``.
        offset_value: Offset applied to the OCV before bookkeeping.

    Returns:
        List with a single CALC ``keep_min_ocv`` action that exports the
        running minimum to the orch global ``new_min_OCV``.
    """

    apm = ActionPlanMaker()  # exposes function parameters via apm.pars
    apm.add(
        CALC_server,
        "keep_min_ocv",
        {
            "min_offset_ocv": min_offset_ocv,
            "new_ocv": new_ocv,
            "offset_value": offset_value,
        },
        to_global_params={"result": "new_min_OCV"},
    )

    return apm.planned_actions  # returns complete action list to orch


# implement Biologic trigger actions
#  chain techniques on one channel with the BIOLOGIC run_plan endpoint

# HISPEC_sub_OCVtoCAtoCV -- use OCV potential for conditioning CA and starting CV; CV needs to locally queue after CA
# HISPEC_sub_EIS

# HISPEC_sub_LoSpEC -- CA to SpEC, conditional SpEC
# HISPEC_sub_PD_LoSpEC


@experiment(version=1)
def HISPEC_sub_CA(
    Vval__V: float = 0.0,
    Tval__s: float = 10.0,
    AcqInterval__s: float = 0.1,  # Time between data acq in seconds.
    IRange: str = "m1",
    ERange: str = "v10",
    Bandwidth: str = "BW4",
    channel: int = 0,
    TTLwait: int = -1,
    TTLsend: int = -1,
) -> list:
    """Run a single chronoamperometry step on the PSTAT server.

    Args:
        Vval__V: Applied potential (V).
        Tval__s: Step duration in seconds.
        AcqInterval__s: Sample interval in seconds.
        IRange: Current range string accepted by the driver.
        ERange: Potential range string accepted by the driver.
        Bandwidth: Bandwidth setting accepted by the driver.
        channel: Potentiostat channel index.
        TTLwait: TTL-in trigger channel (-1 disables).
        TTLsend: TTL-out trigger channel (-1 disables).

    Returns:
        List with a single PSTAT ``run_CA`` action tagged with technique ``CA``.
    """
    apm = ActionPlanMaker()  # exposes function parameters via apm.pars
    apm.add(
        PSTAT_server,
        "run_CA",
        {
            "Vval__V": Vval__V,
            "Tval__s": Tval__s,
            "AcqInterval__s": AcqInterval__s,
            "IRange": IRange,
            "ERange": ERange,
            "Bandwidth": Bandwidth,
            "channel": channel,
            "TTLwait": TTLwait,
            "TTLsend": TTLsend,
        },
        from_global_act_params={"_fast_samples_in": "fast_samples_in"},
        start_condition=ActionStartCondition.wait_for_previous,
        technique_name="CA",
        process_finish=False,
        process_contrib=[
            ProcessContrib.files,
            ProcessContrib.samples_in,
            ProcessContrib.samples_out,
        ],
    )
    return apm.planned_actions  # returns complete action list to orch


@experiment(version=2)
def HISPEC_sub_OCV(
    Tval__s: float = 1,
    SampleRate: float = 0.05,
) -> list:
    """Query the loaded sample then run an OCV step and update the min-OCV tracker.

    Args:
        Tval__s: OCV measurement duration in seconds.
        SampleRate: Sample interval in seconds.

    Returns:
        List of PAL/PSTAT/CALC actions: sample query, PSTAT ``run_OCV`` (tagged
        technique ``OCV``), and a CALC ``keep_min_ocv`` step.
    """
    apm = ActionPlanMaker()  # exposes function parameters via apm.pars
    apm.add(
        SAMPLE_server,
        "archive_custom_query_sample",
        {
            "custom": "cell1_we",
        },
        to_global_params=[
            "_fast_samples_in"
        ],  # save new liquid_sample_no of eche cell to globals
        start_condition=ActionStartCondition.wait_for_all,  # orch is waiting for all action_dq to finish
    )
    apm.add(
        PSTAT_server,
        "run_OCV",
        {
            "Tval__s": Tval__s,
            "AcqInterval__s": SampleRate,
            "TTLwait": -1,  # -1 disables, else select TTL 0-3
            "TTLsend": -1,  # -1 disables, else select TTL 0-3
            # "IErange": "auto",
        },
        from_global_act_params={"_fast_samples_in": "fast_samples_in"},
        start_condition=ActionStartCondition.wait_for_all,  # orch is waiting for all action_dq to finish
        technique_name="OCV",
        process_finish=True,
        process_contrib=[
            ProcessContrib.files,
            ProcessContrib.samples_in,
            ProcessContrib.samples_out,
        ],
        to_global_params={"Ewe_V__mean_final": "HISPEC_OCV"},
    )

    apm.add(
        CALC_server,
        "keep_min_ocv",
        {},
        from_global_act_params={
            "HISPEC_OCV": "new_ocv",
            "min_offset_ocv": "min_offset_ocv",
        },
        to_global_params={"min_offset_ocv": "min_offset_ocv"},
    )
    return apm.planned_actions  # returns complete action list to orch


# spectral electrochemistry experiment
@experiment(version=1)
def HISPEC_sub_SpEC(
    # OCV_vsRef: float = 0.2,
    # Vinit_vsRHE: float = 0.0,  # Initial value in volts or amps.
    Vapex1_vsRHE: float = 1.2,  # Apex 1 value in volts or amps.
    Vapex2_vsRHE: float = -1.0,  # Apex 2 value in volts or amps.
    # Vfinal_vsRHE: float = 0.0,  # Final value in volts or amps.
    scanrate_voltsec: float = 0.002,  # scan rate in volts/second or amps/second.
    samplerate_sec: float = 0.1,
    cycles: int = 1,
    # gamry_i_range: str = "auto",
    gamrychannelwait: int = -1,
    gamrychannelsend: int = 0,
    IRange: str = "m1",
    ERange: str = "v10",
    Bandwidth: str = "BW4",
    solution_ph: float = 0,
    ref_vs_nhe: float = 0.0,
    toggle1_source: str = "spec_trig",
    toggle1_init_delay: float = 0.0,
    toggle1_duty: float = 0.001,
    toggle1_period: float = 10,
    toggle1_time: float = 1,
    # toggle2_source: str = "spec_trig",
    # toggle2_init_delay: float = 0.0,
    # toggle2_duty: float = 0.5,
    # toggle2_period: float = 2.0,
    # toggle2_time: float = -1,
    comment: str = "",
) -> list:
    """Run a spectro-electrochemistry sweep: trigger Andor acquisition and CV.

    Computes the CV duration from the apex/scan-rate parameters, queries the
    loaded sample, arms the Andor camera for external-triggered acquisition,
    waits briefly, then issues a PSTAT ``run_CV`` whose vertices are shifted
    against the supplied reference and pH.

    Args:
        Vapex1_vsRHE: First CV vertex vs RHE in volts.
        Vapex2_vsRHE: Second CV vertex vs RHE in volts.
        scanrate_voltsec: Scan rate in V/s.
        samplerate_sec: Sample interval in seconds.
        cycles: Number of CV cycles.
        gamrychannelwait: PSTAT TTL-in channel (-1 disables).
        gamrychannelsend: PSTAT TTL-out channel (-1 disables).
        IRange: Current range string.
        ERange: Potential range string.
        Bandwidth: Bandwidth setting.
        solution_ph: pH for RHE conversion.
        ref_vs_nhe: Reference offset vs NHE.
        toggle1_source: IO output name used for the spectro trigger.
        toggle1_init_delay: Initial delay before the toggle (s).
        toggle1_duty: Duty cycle (0-1).
        toggle1_period: Toggle period in seconds.
        toggle1_time: Toggle duration; ``-1`` means use the CV duration.
        comment: Free-form comment recorded with the action params.

    Returns:
        List of PAL, Andor, ORCH, and PSTAT actions composing the SpEC run.
    """

    apm = ActionPlanMaker()  # exposes function parameters via apm.pars

    apm.add(
        SAMPLE_server,
        "archive_custom_query_sample",
        {
            "custom": "cell1_we",
        },
        to_global_params=[
            "_fast_samples_in"
        ],  # save new liquid_sample_no of eche cell to globals
        start_condition=ActionStartCondition.wait_for_all,  # orch is waiting for all action_dq to finish
    )

    CV_duration_sec = (
        abs(Vapex1_vsRHE - Vapex2_vsRHE) / scanrate_voltsec
    )  # time from initial to Vertex 1
    CV_duration_sec += (
        abs(Vapex2_vsRHE - Vapex2_vsRHE) / scanrate_voltsec
    )  # time from vertex 1 to vertex 2 (imagine for now num scans =1)
    CV_duration_sec += (
        abs(Vapex2_vsRHE - Vapex1_vsRHE) / scanrate_voltsec
    )  # time from vertex to to final
    CV_duration_sec += (
        abs(Vapex2_vsRHE - Vapex1_vsRHE)
        / scanrate_voltsec
        * 2.0
        * (
            cycles - 1
        )  # now, if C>1 we have c-1 triangular waveforms inserted after the first vertex 1.
    )

    if int(round(toggle1_time)) == -1:
        toggle1_time = CV_duration_sec
    # if int(round(toggle2_time)) == -1:
    #     toggle2_time = CV_duration_sec

    # setup Andor camera external trigger acquisition
    apm.add(
        ANDOR_server,
        "acquire",
        {
            "external_trigger": True,
            "duration": CV_duration_sec * 1.05,
            "frames_per_poll": 100,
            "buffer_count": 10,
            "exp_time": 0.0098,
            "framerate": 98,
            "timeout": 15000,
        },
        sync_data=False,
        from_global_act_params={"_fast_samples_in": "fast_samples_in"},
        start_condition=ActionStartCondition.wait_for_all,  # orch is waiting for all action_dq to finish
        technique_name="CV",
        process_finish=False,
        process_contrib=[
            ProcessContrib.action_params,
            ProcessContrib.files,
            ProcessContrib.samples_in,
            ProcessContrib.samples_out,
        ],
    )

    apm.add(
        ORCH_server,
        "wait",
        {
            "waittime": 3,
        },
        start_condition=ActionStartCondition.no_wait,
    )

    # # setup toggle on galil_io
    # apm.add(
    #     IO_server,
    #     "set_digital_cycle",
    #     {
    #         "trigger_name": "gamry_ttl0",
    #         "triggertype": 1,  # rising edge
    #         "out_name": ["spec_trig", toggle1_source],  # TODO: parameterize outs
    #         "out_name_gamry": None,
    #         "toggle_init_delay": [toggle1_init_delay, toggle1_init_delay],
    #         "toggle_duty": [toggle1_duty, toggle1_duty],
    #         "toggle_period": [toggle1_period, toggle1_period],
    #         "toggle_duration": [toggle1_time, toggle1_time],
    #     },
    #     start_condition=ActionStartCondition.wait_for_previous,  # orch is waiting for all action_dq to finish
    #     process_finish=False,
    #     process_contrib=[ProcessContrib.files, ProcessContrib.samples_out],
    # )

    # apply potential
    apm.add(
        PSTAT_server,
        "run_CV",
        {
            "Vinit__V": Vapex2_vsRHE - 1.0 * ref_vs_nhe - 0.059 * solution_ph,
            "Vapex1__V": Vapex1_vsRHE - 1.0 * ref_vs_nhe - 0.059 * solution_ph,
            "Vapex2__V": Vapex2_vsRHE - 1.0 * ref_vs_nhe - 0.059 * solution_ph,
            "Vfinal__V": Vapex2_vsRHE - 1.0 * ref_vs_nhe - 0.059 * solution_ph,
            "ScanRate__V_s": scanrate_voltsec,
            "AcqInterval__s": samplerate_sec,
            "Cycles": cycles,
            "TTLwait": gamrychannelwait,  # -1 disables, else select TTL 0-3
            "TTLsend": gamrychannelsend,  # -1 disables, else select TTL 0-3
            "IRange": IRange,
            "ERange": ERange,
            "Bandwidth": Bandwidth,
        },
        from_global_act_params={"_fast_samples_in": "fast_samples_in"},
        start_condition=ActionStartCondition.wait_for_previous,
        technique_name="CV",
        process_finish=True,
        process_contrib=[
            ProcessContrib.action_params,
            ProcessContrib.files,
            ProcessContrib.samples_in,
            ProcessContrib.samples_out,
        ],
    )
    return apm.planned_actions  # returns complete action list to orch


@experiment(version=1)
def HISPEC_sub_CP(
    Ival__A: float = 0.0,
    Tval__s: float = 10.0,
    AcqInterval__s: float = 0.1,  # Time between data acq in seconds.
    IRange: str = "m1",
    ERange: str = "v10",
    Bandwidth: str = "BW4",
    channel: int = 0,
    TTLwait: int = -1,
    TTLsend: int = -1,
    TTLduration: float = 1.0,
    # alert_duration__s: float = -1,
    # alert_above: bool = True,
    # alert_sleep__s: float = -1,
    # alertThreshEwe_V: float = 0,
) -> list:
    """Query the cell sample then run a chronopotentiometry step with bounds check.

    Args:
        Ival__A: Applied current in amps.
        Tval__s: Step duration in seconds.
        AcqInterval__s: Sample interval in seconds.
        IRange: Current range string.
        ERange: Potential range string.
        Bandwidth: Bandwidth setting.
        channel: Potentiostat channel index.
        TTLwait: TTL-in trigger channel (-1 disables).
        TTLsend: TTL-out trigger channel (-1 disables).
        TTLduration: TTL pulse duration (s).

    Returns:
        List of PAL, PSTAT and CALC actions performing the CP step and then a
        bounds check on the resulting final mean Ewe.
    """

    apm = ActionPlanMaker()  # exposes function parameters via apm.pars

    apm.add(
        SAMPLE_server,
        "archive_custom_query_sample",
        {
            "custom": "cell1_we",
        },
        to_global_params=[
            "_fast_samples_in"
        ],  # save new liquid_sample_no of eche cell to globals
        start_condition=ActionStartCondition.wait_for_all,  # orch is waiting for all action_dq to finish
    )
    apm.add(
        action_server=PSTAT_server,
        action_name="run_CP",
        action_params={
            "Ival__A": Ival__A,
            "Tval__s": Tval__s,
            "AcqInterval__s": AcqInterval__s,
            "IRange": IRange,
            "ERange": ERange,
            "Bandwidth": Bandwidth,
            "channel": channel,
            "TTLwait": TTLwait,
            "TTLsend": TTLsend,
            "TTLduration": TTLduration,
        },
        from_global_act_params={"_fast_samples_in": "fast_samples_in"},
        start_condition=ActionStartCondition.wait_for_previous,
        technique_name="CP",
        process_finish=False,
        process_contrib=[
            ProcessContrib.files,
            ProcessContrib.samples_in,
            ProcessContrib.samples_out,
        ],
        # global params has a global scope on the level of the orch
        to_global_params={"Ewe_V__mean_final": "CP_Ewe_V__mean_final"},
    )

    apm.add(
        CALC_server,
        "check_CP_Ewe_bounds",
        {},
        # global act params inherits from global params - we need to call from this to give the correct name
        # consume the value for the action
        from_global_act_params={"CP_Ewe_V__mean_final": "CP_Ewe_V__mean_final"},
        # now write a new value to the global params
        to_global_params={"CP_Ewe_V__mean_final": "CP_Ewe_V__mean_final_limited"},
    )
    return apm.planned_actions


@experiment(version=1)
def HISPEC_sub_PEIS(
    Vinit__V: float = 0.0,  # Initial value in volts or amps.
    Vamp__V: float = 0.01,  # Amplitude value in volts
    Finit__Hz: float = 1,  # Initial frequency in Hz.
    Ffinal__Hz: float = 2000000,  # Final frequency in Hz.
    FrequencyNumber: int = 60,
    Duration__s: float = 0,  # Duration in seconds.
    AcqInterval__s: float = 0.1,  # Time between data acq in seconds.
    SweepMode: str = "log",
    Repeats: int = 10,
    DelayFraction: float = 0.1,
    # vs_initial: bool = False,  # True if vs initial, False if vs previous.
    IRange: str = "m10",
    ERange: str = "v10",
    Bandwidth: str = "BW4",
    channel: int = 0,
    TTLwait: int = -1,
    TTLsend: int = -1,
    TTLduration: float = 1.0,
) -> list:
    """Run a potentio-EIS sweep on the PSTAT server.

    Args:
        Vinit__V: DC bias for the EIS sweep (V).
        Vamp__V: AC amplitude (V).
        Finit__Hz: Initial frequency (Hz).
        Ffinal__Hz: Final frequency (Hz).
        FrequencyNumber: Number of frequency points.
        Duration__s: Total duration (s); 0 lets the driver decide.
        AcqInterval__s: Sample interval (s).
        SweepMode: ``"log"`` or ``"lin"`` frequency sweep.
        Repeats: Number of sweep repeats.
        DelayFraction: Pre-sweep delay fraction.
        IRange: Current range string.
        ERange: Potential range string.
        Bandwidth: Bandwidth setting.
        channel: Potentiostat channel index.
        TTLwait: TTL-in trigger channel (-1 disables).
        TTLsend: TTL-out trigger channel (-1 disables).
        TTLduration: TTL pulse duration (s).

    Returns:
        List with a single PSTAT ``run_PEIS`` action tagged ``PEIS``.
    """

    apm = ActionPlanMaker()  # exposes function parameters via apm.pars
    apm.add(
        action_server=PSTAT_server,
        action_name="run_PEIS",
        action_params={
            "Vinit__V": Vinit__V,
            "Vamp__V": Vamp__V,
            "Finit__Hz": Finit__Hz,
            "Ffinal__Hz": Ffinal__Hz,
            "FrequencyNumber": FrequencyNumber,
            "Duration__s": Duration__s,
            "AcqInterval__s": AcqInterval__s,
            "SweepMode": SweepMode,
            "Repeats": Repeats,
            "DelayFraction": DelayFraction,
            "IRange": IRange,
            "ERange": ERange,
            "Bandwidth": Bandwidth,
            "channel": channel,
            "TTLwait": TTLwait,
            "TTLsend": TTLsend,
            "TTLduration": TTLduration,
        },
        from_global_act_params={"_fast_samples_in": "fast_samples_in"},
        start_condition=ActionStartCondition.wait_for_previous,
        technique_name="PEIS",
        process_finish=False,
        process_contrib=[
            ProcessContrib.files,
            ProcessContrib.samples_in,
            ProcessContrib.samples_out,
        ],
    )
    return apm.planned_actions  # returns complete action list to orch
