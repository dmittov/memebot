from memebot.censor import SimpleTimeCensor
from pytest import mark

@mark.integration
class TestSimpleTimeCensor:

    def test_check(self, firestore_emulator: str) -> None:
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        censor_result = censor.check(666)
        assert censor_result.is_allowed == True
