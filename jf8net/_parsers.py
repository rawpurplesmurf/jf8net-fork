"""
jf8net._parsers — Convert raw API dicts to typed model objects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ._models import (
    BandEntry,
    ClearFreqResult,
    Config,
    DecodedMessage,
    FrameUpdate,
    HeartbeatEntry,
    InboxMessage,
    PassbandSlot,
    PassbandState,
    QsoEntry,
    RadioStatus,
    Spectrum,
    Status,
    TxFrame,
    VersionInfo,
)


def _utc(iso: str) -> datetime:
    if not iso:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(tz=timezone.utc)


def parse_decoded_message(d: dict[str, Any]) -> DecodedMessage:
    return DecodedMessage(
        time=_utc(str(d.get("utc_iso", ""))),
        freq_hz=float(d.get("freq_hz", 0)),
        snr_db=int(d.get("snr_db", 0)),
        submode=int(d.get("submode", 0)),
        submode_name=str(d.get("submode_name", "")),
        from_call=str(d.get("from", "")),
        to=str(d.get("to", "")),
        body=str(d.get("body", "")),
        raw=str(d.get("raw", "")),
        type=int(d.get("type", 0)),
        type_name=str(d.get("type_name", "")),
        grid=str(d.get("grid", "")),
        dist_km=float(d.get("dist_km", -1.0)),
        bearing_deg=float(d.get("bearing_deg", -1.0)),
        heard_me=bool(d.get("heard_me", False)),
        dial_freq_khz=float(d.get("dial_freq_khz", 0.0)),
        spot_freq_khz=float(d.get("spot_freq_khz", 0.0)),
    )


def parse_frame_update(d: dict[str, Any]) -> FrameUpdate:
    return FrameUpdate(
        time=_utc(str(d.get("utc_iso", ""))),
        freq_hz=float(d.get("freq_hz", 0)),
        snr_db=int(d.get("snr_db", 0)),
        submode=int(d.get("submode", 0)),
        submode_name=str(d.get("submode_name", "")),
        frame_type=int(d.get("frame_type", 0)),
        frame_text=str(d.get("frame_text", "")),
        assembled_text=str(d.get("assembled_text", "")),
        is_complete=bool(d.get("is_complete", False)),
        dial_freq_khz=float(d.get("dial_freq_khz", 0.0)),
        spot_freq_khz=float(d.get("spot_freq_khz", 0.0)),
    )


def parse_passband_slot(d: dict[str, Any]) -> PassbandSlot:
    return PassbandSlot(
        hz=int(d.get("hz", 0)),
        age_secs=float(d.get("age_secs", 0.0)),
        call=str(d.get("call", "")),
    )


def parse_passband_state(d: dict[str, Any]) -> PassbandState:
    return PassbandState(
        busy_slots=[parse_passband_slot(s) for s in d.get("busy_slots", [])],
        clear_window_secs=int(d.get("clear_window_secs", 120)),
        bandwidth_hz=float(d.get("bandwidth_hz", 50.0)),
    )


def parse_clear_freq_result(d: dict[str, Any]) -> ClearFreqResult:
    return ClearFreqResult(
        freq_hz=float(d.get("freq_hz", 1500.0)),
        all_clear=bool(d.get("all_clear", True)),
        clear_window_secs=int(d.get("clear_window_secs", 120)),
        queue_size=int(d.get("queue_size", 0)),
    )


def parse_heartbeat_entry(d: dict[str, Any]) -> HeartbeatEntry:
    return HeartbeatEntry(
        callsign=str(d.get("callsign", "")),
        grid=str(d.get("grid", "")),
        snr_db=int(d.get("snr_db", 0)),
        freq_hz=float(d.get("freq_hz", 0.0)),
        dial_khz=float(d.get("dial_khz", 0.0)),
        utc=_utc(str(d.get("utc_iso", ""))),
        age_secs=int(d.get("age_secs", 0)),
        dist_km=float(d.get("dist_km", -1.0)),
        bearing_deg=float(d.get("bearing_deg", -1.0)),
        hb_count=int(d.get("hb_count", 1)),
        is_ack=bool(d.get("is_ack", False)),
        acked_by_me=bool(d.get("acked_by_me", False)),
        last_payload=str(d.get("last_payload", "")),
    )


def parse_status(d: dict[str, Any]) -> Status:
    return Status(
        callsign=str(d.get("callsign", "")),
        grid=str(d.get("grid", "")),
        submode=int(d.get("submode", 0)),
        submode_name=str(d.get("submode_name", "")),
        frequency_khz=float(d.get("frequency_khz", 0)),
        tx_freq_hz=float(d.get("tx_freq_hz", 0)),
        transmitting=bool(d.get("transmitting", False)),
        audio_running=bool(d.get("audio_running", False)),
        radio_connected=bool(d.get("radio_connected", False)),
        radio_freq_khz=float(d.get("radio_freq_khz", 0)),
        radio_mode=str(d.get("radio_mode", "")),
        tx_queue_size=int(d.get("tx_queue_size", 0)),
        heartbeat_enabled=bool(d.get("heartbeat_enabled", False)),
        heartbeat_interval_mins=int(d.get("heartbeat_interval_mins", 10)),
        auto_reply=bool(d.get("auto_reply", False)),
        ws_port=int(d.get("ws_port", 2102)),
        ws_clients=int(d.get("ws_clients", 0)),
        bandwidth_hz=float(d.get("bandwidth_hz", 50.0)),
        rigctld=str(d.get("rigctld", "127.0.0.1:4532")),
        rig_model=int(d.get("rig_model", 2)),
        heartbeat_secs_remaining=int(d.get("heartbeat_secs_remaining", -1)),
        heartbeat_sub_channel=bool(d.get("heartbeat_sub_channel", True)),
        heartbeat_ack_enabled=bool(d.get("heartbeat_ack_enabled", False)),
        clear_bin_window_secs=int(d.get("clear_bin_window_secs", 120)),
        tx_enabled=bool(d.get("tx_enabled", True)),
        ws_host=str(d.get("ws_host", "127.0.0.1")),
        carrier_freq_khz=float(d.get("carrier_freq_khz", d.get("frequency_khz", 0.0))),
        data_offset_hz=int(d.get("data_offset_hz", 0)),
        busy_slots=[parse_passband_slot(s) for s in d.get("busy_slots", [])],
    )


def parse_band_entry(d: dict[str, Any]) -> BandEntry:
    return BandEntry(
        name=str(d.get("name", "")),
        freq_khz=float(d.get("freqKhz", 14078.0)),
        tx_freq_hz=float(d.get("txFreqHz", 1500.0)),
    )


def parse_qso_entry(d: dict[str, Any]) -> QsoEntry:
    return QsoEntry(
        id=str(d.get("id", "")),
        time=_utc(str(d.get("time", ""))),
        callsign=str(d.get("callsign", "")),
        grid=str(d.get("grid", "")),
        snr_db=int(d.get("snr_db", 0)),
        notes=str(d.get("notes", "")),
    )


def parse_inbox_message(d: dict[str, Any]) -> InboxMessage:
    return InboxMessage(
        id=int(d.get("id", 0)),
        utc=_utc(str(d.get("utc_iso", ""))),
        from_call=str(d.get("from", "")),
        to=str(d.get("to", "")),
        body=str(d.get("body", "")),
        read=bool(d.get("read", False)),
        delivered=bool(d.get("delivered", False)),
    )


def parse_config(d: dict[str, Any]) -> Config:
    band_list = [parse_band_entry(b) for b in (d.get("bandList") or [])]
    groups_raw = d.get("groups")
    if isinstance(groups_raw, list):
        groups = [str(g) for g in groups_raw]
    else:
        groups = ["@ALL", "@ALLCALL"]
    raw_port = d.get("rigPort") or d.get("rigctld") or "127.0.0.1:4532"
    rig_port = str(raw_port)
    rigctld_val = str(d.get("rigctld") or rig_port)
    return Config(
        callsign=str(d.get("callsign", "")),
        grid=str(d.get("grid", "")),
        audio_input_name=str(d.get("audioInputName", "")),
        audio_output_name=str(d.get("audioOutputName", "")),
        modem_type=int(d.get("modemType", 0)),
        submode=int(d.get("submode", 0)),
        frequency_khz=float(d.get("frequencyKhz", 0)),
        tx_freq_hz=float(d.get("txFreqHz", 0)),
        tx_power_pct=int(d.get("txPowerPct", 50)),
        heartbeat_enabled=bool(d.get("heartbeatEnabled", False)),
        auto_reply=bool(d.get("autoReply", False)),
        station_info=str(d.get("stationInfo", "")),
        station_status=str(d.get("stationStatus", "")),
        cq_message=str(d.get("cqMessage", "")),
        dist_miles=bool(d.get("distMiles", False)),
        auto_atu=bool(d.get("autoAtu", False)),
        psk_reporter_enabled=bool(d.get("pskReporterEnabled", True)),
        rig_model=int(d.get("rigModel", 2)),
        rig_port=rig_port,
        rigctld=rigctld_val,
        rig_baud=int(d.get("rigBaud", 9600)),
        rig_data_bits=int(d.get("rigDataBits", 8)),
        rig_stop_bits=int(d.get("rigStopBits", 1)),
        rig_parity=int(d.get("rigParity", 0)),
        rig_handshake=int(d.get("rigHandshake", 0)),
        rig_dtr_state=int(d.get("rigDtrState", 2)),
        rig_rts_state=int(d.get("rigRtsState", 2)),
        ptt_type=int(d.get("pttType", 1)),
        emulated_split=bool(d.get("emulatedSplit", False)),
        ws_enabled=bool(d.get("wsEnabled", True)),
        ws_port=int(d.get("wsPort", 2102)),
        ws_host=str(d.get("wsHost", "127.0.0.1")),
        web_host=str(d.get("webHost", "127.0.0.1")),
        web_port=int(d.get("webPort", 0)),
        data_offset_hz=int(d.get("dataOffsetHz", 0)),
        heartbeat_interval_mins=int(d.get("heartbeatIntervalMins", 10)),
        heartbeat_sub_channel=bool(d.get("heartbeatSubChannel", True)),
        heartbeat_ack_enabled=bool(d.get("heartbeatAckEnabled", False)),
        clear_bin_window_secs=int(d.get("clearBinWindowSecs", 120)),
        tx_enabled=bool(d.get("txEnabled", True)),
        info_max_age_mins=int(d.get("infoMaxAgeMins", 30)),
        heard_max_age_mins=int(d.get("heardMaxAgeMins", 30)),
        groups=groups,
        band_list=band_list,
    )


def parse_radio_status(d: dict[str, Any]) -> RadioStatus:
    port = str(d.get("port", ""))
    return RadioStatus(
        connected=bool(d.get("connected", False)),
        freq_khz=float(d.get("freq_khz", 0)),
        mode=str(d.get("mode", "")),
        rig_model=int(d.get("rig_model", 2)),
        port=port,
        rigctld=str(d.get("rigctld", port)),
        baud=int(d.get("baud", 9600)),
        data_bits=int(d.get("data_bits", 8)),
        stop_bits=int(d.get("stop_bits", 1)),
        parity=int(d.get("parity", 0)),
        handshake=int(d.get("handshake", 0)),
        dtr_state=int(d.get("dtr_state", 2)),
        rts_state=int(d.get("rts_state", 2)),
        ptt_type=int(d.get("ptt_type", 1)),
    )


def parse_tx_frame(d: dict[str, Any]) -> TxFrame:
    return TxFrame(
        payload=str(d.get("payload", "")),
        frame_type=int(d.get("frame_type", 0)),
        submode=int(d.get("submode", 0)),
        tx_freq_hz=float(d.get("tx_freq_hz", 1500.0)),
    )


def parse_spectrum(d: dict[str, Any]) -> Spectrum:
    return Spectrum(
        bins=[float(v) for v in d.get("bins", [])],
        bin_count=int(d.get("bin_count", 0)),
        hz_per_bin=float(d.get("hz_per_bin", 0)),
        sample_rate=float(d.get("sample_rate", 12000)),
    )


_SNAKE_TO_CAMEL = {
    "callsign": "callsign",
    "grid": "grid",
    "audio_input_name": "audioInputName",
    "audio_output_name": "audioOutputName",
    "modem_type": "modemType",
    "submode": "submode",
    "frequency_khz": "frequencyKhz",
    "data_offset_hz": "dataOffsetHz",
    "tx_freq_hz": "txFreqHz",
    "tx_power_pct": "txPowerPct",
    "heartbeat_enabled": "heartbeatEnabled",
    "heartbeat_interval_mins": "heartbeatIntervalMins",
    "heartbeat_sub_channel": "heartbeatSubChannel",
    "heartbeat_ack_enabled": "heartbeatAckEnabled",
    "clear_bin_window_secs": "clearBinWindowSecs",
    "auto_reply": "autoReply",
    "station_info": "stationInfo",
    "station_status": "stationStatus",
    "cq_message": "cqMessage",
    "groups": "groups",
    "dist_miles": "distMiles",
    "auto_atu": "autoAtu",
    "psk_reporter_enabled": "pskReporterEnabled",
    "rigctld": "rigctld",
    "rig_model": "rigModel",
    "rig_port": "rigPort",
    "rig_baud": "rigBaud",
    "rig_data_bits": "rigDataBits",
    "rig_stop_bits": "rigStopBits",
    "rig_parity": "rigParity",
    "rig_handshake": "rigHandshake",
    "rig_dtr_state": "rigDtrState",
    "rig_rts_state": "rigRtsState",
    "ptt_type": "pttType",
    "emulated_split": "emulatedSplit",
    "ws_enabled": "wsEnabled",
    "ws_host": "wsHost",
    "ws_port": "wsPort",
    "web_host": "webHost",
    "web_port": "webPort",
    "tx_enabled": "txEnabled",
    "info_max_age_mins": "infoMaxAgeMins",
    "heard_max_age_mins": "heardMaxAgeMins",
}


def config_kwargs_to_api(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Convert set_config() keyword arguments to API field names."""
    result: dict[str, Any] = {}
    for k, v in kwargs.items():
        api_key = _SNAKE_TO_CAMEL.get(k)
        if api_key is None:
            if k in _SNAKE_TO_CAMEL.values():
                api_key = k
            else:
                raise ValueError(
                    f"Unknown config field: {k!r}. Valid fields: {sorted(_SNAKE_TO_CAMEL)}"
                )
        result[api_key] = v
    return result


def parse_version_info(d: dict[str, Any]) -> VersionInfo:
    return VersionInfo(
        version=str(d.get("version", "")),
        major=int(d.get("major", 0)),
        minor=int(d.get("minor", 0)),
        patch=int(d.get("patch", 0)),
        release=str(d.get("release", "RELEASE")),
    )
