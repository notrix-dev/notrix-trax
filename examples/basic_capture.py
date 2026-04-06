"""Minimal example showing local Trax capture."""

from trax.sdk import end_run, start_run, trace_step


def main() -> None:
    run = start_run("basic-example", input_payload={"script": "basic_capture.py"})
    trace_step(
        "prepare-input",
        input_payload={"question": "hello"},
        output_payload={"normalized_question": "hello"},
        attributes={"semantic_type": "transform", "safety_level": "safe_read"},
    )
    end_run(output_payload={"run_id": run.id})
    print(run.id)


if __name__ == "__main__":
    main()
