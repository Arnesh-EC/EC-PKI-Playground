"""Slice-12 sequences: webServerCert (IIS/OCSP) + client enrollment tail on
domainJoin (pure)."""

import json
import os

os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SETTINGS_ENC_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")

from app.core.sequences.definitions import op_sequence  # noqa: E402
from app.core.sequences.model import DnsRecordContext, NodeContext, RunContext  # noqa: E402


def _node(nid, vm, template, cfg=None, ip="192.168.1.1"):
    return NodeContext(
        node_id=nid, vm_name=vm, hostname=vm, agent_vm_id=f"v-{nid}",
        ip=ip, template_id=template, template_config=cfg or {},
    )


def _web_ctx():
    dc = _node("dc01", "guest-abc12-dc01", "domainController",
               {"domainName": "encon.pki", "netbiosName": "ENCON",
                "domainAdminPassword": "Str0ng-Lab-Pass!"})
    ca = _node("ca02", "guest-abc12-ca02", "certificateAuthority",
               {"caType": "Issuing", "commonName": "EncryptionConsulting Issuing CA"})
    web = _node("srv1", "guest-abc12-srv1", "webServer",
                {"certEnrollPath": "C:\\CertEnroll", "ocspRefreshMinutes": "15"})
    return RunContext(
        nodes={"primary": web, "secondary": ca, "ca": ca, "dc": dc, "web": web},
        domain_name="encon.pki",
        netbios="ENCON",
        pki_host="pki.encon.pki",
        dns_records=(
            DnsRecordContext(
                id="dns:cname:dc01:pki",
                kind="CNAME",
                server="dc01",
                subject="srv1",
                zone="encon.pki",
                name="pki",
            ),
        ),
    )


def test_web_server_cert_sequence_shape():
    steps = op_sequence("webServerCert", _web_ctx())
    commands = [s.command for s in steps]
    assert commands == [
        "iis.setup_certenroll",
        "ocsp.install",
        "cert.enroll",
        "ocsp.configure_revocation",
        "dns.apply_resources",
        "dns.verify",
        "dns.verify",
        "cert.enroll",
    ]


def test_web_iis_step_is_the_web_half():
    ctx = _web_ctx()
    iis = op_sequence("webServerCert", ctx)[0]
    assert iis.resolve_params(ctx)["scope"] == "web"


def test_ocsp_config_points_at_the_issuing_ca():
    ctx = _web_ctx()
    cfg = next(s for s in op_sequence("webServerCert", ctx) if s.id == "ocsp-config")
    params = cfg.resolve_params(ctx)
    assert params["caConfig"] == (
        "guest-abc12-ca02.encon.pki\\EncryptionConsulting Issuing CA"
    )
    assert params["refreshMinutes"] == "15"
    assert cfg.verify.command == "ocsp.verify"


def test_deferred_cname_targets_the_web_host_on_the_dc():
    ctx = _web_ctx()
    cname = next(s for s in op_sequence("webServerCert", ctx) if s.id == "dns-cname-apply")
    assert cname.target == "dc"
    params = cname.resolve_params(ctx)
    assert json.loads(params["records"])[0] == {
        "id": "dns:cname:dc01:pki",
        "kind": "CNAME",
        "name": "pki",
        "value": "guest-abc12-srv1.encon.pki.",
        "zone": "encon.pki",
    }


def test_cname_and_http_are_verified_from_web_and_ca():
    ctx = _web_ctx()
    verify = [
        step for step in op_sequence("webServerCert", ctx)
        if step.command == "dns.verify"
    ]
    assert [step.target for step in verify] == ["primary", "ca"]
    assert all(
        step.resolve_params(ctx)["httpUrl"] == "http://pki.encon.pki/CertEnroll/"
        for step in verify
    )


def test_web_sequence_enrolls_a_dedicated_health_probe():
    ctx = _web_ctx()
    enroll = next(
        step for step in op_sequence("webServerCert", ctx)
        if step.id == "enroll-health-probe"
    )

    assert enroll.target == "primary"
    assert enroll.resolve_params(ctx) == {
        "template": "Workstation",
        "exportPath": "C:\\Transfer\\lab-health-probe.cer",
        "refreshPolicy": "true",
    }


def _client_ctx(with_ca=True):
    dc = _node("dc01", "guest-abc12-dc01", "domainController",
               {"domainName": "encon.pki", "netbiosName": "ENCON",
                "domainAdminPassword": "Str0ng-Lab-Pass!"})
    win11 = _node("win11", "guest-abc12-win11", "client")
    nodes = {"primary": win11, "secondary": dc, "dc": dc}
    if with_ca:
        nodes["ca"] = _node("ca02", "guest-abc12-ca02", "certificateAuthority",
                            {"caType": "Issuing"})
    return RunContext(
        nodes=nodes,
        domain_name="encon.pki",
        netbios="ENCON",
    )


def test_client_join_appends_enroll_and_verify():
    steps = op_sequence("domainJoin", _client_ctx(with_ca=True))
    enroll = steps[-1]
    assert enroll.command == "cert.enroll"
    p = enroll.resolve_params(_client_ctx())
    assert p["template"] == "Workstation"
    assert p["exportPath"] == "C:\\win11.cer"
    assert enroll.verify.command == "cert.verify"
    assert enroll.verify_predicate({"chain_ok": True}) is True


def test_client_join_without_a_ca_skips_enrollment():
    steps = op_sequence("domainJoin", _client_ctx(with_ca=False))
    assert all(s.command != "cert.enroll" for s in steps)
