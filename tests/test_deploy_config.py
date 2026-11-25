"""배포 설정 파일끼리 서로 맞는지 검사한다. (포트, 헬스체크 경로, 문서 링크)"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_port_is_consistent_across_nginx_dockerfile_and_cloud_run():
    assert "listen 8080;" in read("docker/nginx.conf")
    dockerfile = read("Dockerfile")
    assert "EXPOSE 8080" in dockerfile and "127.0.0.1:8080/healthz" in dockerfile
    deploy = read(".github/workflows/deploy-cloudrun.yml")
    assert "--port 8080" in deploy and "httpGet.port=8080" in deploy


def test_health_endpoint_is_defined_and_used_everywhere():
    assert "location = /healthz" in read("docker/nginx.conf")
    assert "/healthz" in read("scripts/docker_smoke.sh")
    assert "/healthz" in read("scripts/healthcheck.py")
    assert "httpGet.path=/healthz" in read(".github/workflows/deploy-cloudrun.yml")
    assert 'path /healthz' in read("infra/gcp/monitoring.sh")


def test_build_arg_for_version_is_passed_on_every_image_build():
    workflow = read(".github/workflows/docker.yml")
    assert workflow.count("GIT_SHA=${{ github.sha }}") == 2
    assert "ARG GIT_SHA" in read("Dockerfile") and "version.json" in read("Dockerfile")


def test_dockerignore_allows_what_the_dockerfile_copies():
    ignore = read(".dockerignore").splitlines()
    for needed in ("!dashboard/", "!docker/"):
        assert needed in ignore


def test_deploy_workflow_does_not_run_without_configuration_and_never_uses_key_files():
    text = read(".github/workflows/deploy-cloudrun.yml")
    assert "needs.config.outputs.enabled == 'true'" in text
    assert "credentials_json" not in text and "GOOGLE_APPLICATION_CREDENTIALS" not in text
    assert "workload_identity_provider" in text


@pytest.mark.parametrize("name", ["alert-uptime", "alert-5xx", "alert-latency"])
def test_alert_policies_are_valid_and_use_known_placeholders(name):
    text = read(f"infra/gcp/monitoring/{name}.yaml")
    doc = yaml.safe_load(text)
    assert doc["displayName"] and doc["conditions"] and doc["notificationChannels"] == ["__CHANNEL__"]
    assert set(re.findall(r"__[A-Z_]+__", text)) <= {"__CHECK_ID__", "__CHANNEL__", "__SERVICE__"}


def test_monitoring_script_handles_every_alert_file_it_ships():
    script = read("infra/gcp/monitoring.sh")
    assert "alert-*.yaml" in script
    assert {p.name for p in (ROOT / "infra/gcp/monitoring").glob("alert-*.yaml")} == {
        "alert-5xx.yaml", "alert-latency.yaml", "alert-uptime.yaml"}


@pytest.mark.parametrize("doc", sorted((ROOT / "docs" / "deploy").glob("*.md")), ids=lambda p: p.name)
def test_relative_links_in_deploy_docs_resolve(doc):
    for target in re.findall(r"\]\((?!https?://|#)([^)#]+)", doc.read_text(encoding="utf-8")):
        assert (doc.parent / target).resolve().exists(), f"{doc.name}: {target}"


def test_preview_workflows_split_validation_from_deployment():
    preview = yaml.safe_load(read(".github/workflows/pages-preview.yml"))
    deploy = yaml.safe_load(read(".github/workflows/pages-preview-deploy.yml"))
    assert preview["permissions"] == {"contents": "read"}   # 검증 단계는 읽기만
    triggers = deploy.get("on", deploy.get(True))
    assert triggers["workflow_run"]["workflows"] == ["Pages Preview"]
    assert deploy["concurrency"]["group"] == read(".github/workflows/deploy-pages.yml").split("group: ")[1].split()[0]
