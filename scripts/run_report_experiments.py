"""Reproduce report experiments without changing submitted YAML or simulator."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import run_scenario, evaluate_checks
from gameday_lab.factory import build_client

def config(scenarios):
    return load_config(str(ROOT / "configs/gameday.yaml"), str(ROOT / "configs" / scenarios))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def main():
    unlimited = dict(retry_budget_ratio=100, retry_budget_max_tokens=1e9, retry_budget_min_per_s=1e6)
    stress = dict(breaker=dict(min_calls=1000000000), max_attempts_per_provider=5)
    results = {}
    for label, changes, tapes in [
        ("budget_on", stress, ["G2_overload_storm", "G3_brownout"]),
        ("budget_off", {**stress, **unlimited}, ["G2_overload_storm", "G3_brownout"]),
        ("normal_budget_off", unlimited, ["G2_overload_storm", "G3_brownout"]),
        ("timeout_30", dict(attempt_timeout_s=30), ["G4_slow_region", "G6_provider_outage"]),
        ("unfiltered", {}, ["G6_provider_outage"]),
    ]:
        for tape in tapes:
            cfg = config("scenarios.yaml")
            for key, value in changes.items():
                if isinstance(value, dict):
                    cfg.client[key].update(value)
                else:
                    cfg.client[key] = value
            client = build_client("resilient", cfg)
            if label == "unfiltered":
                client.ladder = lambda task: list(client.order)
            results[label + "_" + tape] = run_scenario(cfg, tape, client, 25).metrics()
    save(ROOT / "reports/experiments/part_f.json", results)
    for label, changes in [
        ("threshold_080", dict(similarity_threshold=.80)), ("threshold_090", {}),
        ("threshold_097", dict(similarity_threshold=.97)), ("ttl_30", dict(ttl_s=30)),
        ("ttl_60", {}), ("ttl_300", dict(ttl_s=300)), ("stale_0", dict(max_stale_s=0)),
    ]:
        cfg = config("scenarios_cache.yaml")
        client = build_client("cached", cfg)
        for key, value in changes.items():
            setattr(client.cache, key, value)
        metrics = run_scenario(cfg, "C1_faq_outage", client, 25).metrics()
        metrics["checks"] = evaluate_checks(metrics, cfg.scenarios["C1_faq_outage"].checks)
        metrics["pass"] = all(metrics["checks"].values())
        save(ROOT / f"reports/cache/experiments/{label}.json", metrics)
    print("Saved report experiments")

if __name__ == "__main__":
    main()
