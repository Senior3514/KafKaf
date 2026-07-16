from kafkaf.core.enrichment import service as enrichment_service
from kafkaf.core.skills.base import Skill


class OwnModelStatusSkill(Skill):
    name = "own_model_status"
    description = (
        "Report how much KafKaf's own private model has actually learned so "
        "far — corpus size and last training run, distinct from searching "
        "what's in it (see memory_search). Argument is ignored."
    )

    async def run(self, arg: str) -> str:
        status = enrichment_service.get_status()
        last_run = status["last_training_run"]
        if last_run:
            run_summary = (
                f"last trained {last_run['steps']} steps at {last_run['created_at']} "
                f"(loss {last_run['loss_start']:.3f} -> {last_run['loss_end']:.3f})"
            )
        else:
            run_summary = "never trained yet"

        return (
            f"corpus: {status['corpus_size']} examples taught "
            f"({status['unused_examples']} not yet trained on)\n"
            f"checkpoint exists: {status['checkpoint_exists']}\n"
            f"{run_summary}"
        )
