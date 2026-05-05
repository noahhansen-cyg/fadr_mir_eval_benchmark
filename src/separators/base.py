from abc import ABC, abstractmethod


class StemSeparator(ABC):
    @abstractmethod
    def separate(self, mixture_path: str, output_dir: str) -> dict:
        """
        Separate a mixture WAV into stems.

        Returns a dict mapping canonical stem name → local WAV path, e.g.:
            {"vocals": "data/separated/fadr/track/vocals.wav", ...}
        """
