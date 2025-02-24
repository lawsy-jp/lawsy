class RRF:
    def __call__(self, runs: list[dict], k: float = 60) -> dict:
        key2score = {}
        for run in runs:
            for i, (key, _) in enumerate(run.items(), start=1):
                key2score[key] = key2score.get(key, 0) + 1 / (k + i)
        return key2score
