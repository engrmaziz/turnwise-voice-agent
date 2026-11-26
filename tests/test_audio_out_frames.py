"""Play-stream frames are 320 samples at 20 ms. Capture indexes are not play indexes."""

from models.tts_cache import TtsCache
from models.tts_pool import TtsPool
from pipeline.event import EventKind
from pipeline.stages.audio_out import AudioOutHandler, pack_frames
from server.playback import PlaybackCursor
from server.transport import MsgType
from tests.conftest import Harness


def test_pack_frames_are_320_samples() -> None:
    frame_bytes = 640
    pcm = b"\x00" * (frame_bytes * 3 + 20)
    frames = pack_frames(pcm, frame_bytes)
    assert len(frames) == 4
    assert all(len(frame) == frame_bytes for frame in frames)
    assert len(frames[0]) // 2 == 320


async def test_play_indexes_start_at_zero_not_capture_index(harness: Harness) -> None:
    sent: list[int] = []

    async def send(data: bytes) -> None:
        assert data[0] == MsgType.PCM
        sent.append(int.from_bytes(data[1:5], "little"))

    pool = TtsPool.stub(timeout_ms=800, frame_bytes=harness.settings.tts_pcm_bytes)
    cache = TtsCache(warmup_ids=frozenset())
    playback = PlaybackCursor()
    handler = AudioOutHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        pool=pool,
        cache=cache,
        playback=playback,
        send=send,
    )
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {
            "text": "hello there friend",
            "voice": "default",
            "speed": 1.0,
            "filler": 0,
            "first_chunk": 1,
        },
        frame_index=99,
    )
    await handler(event)
    pool.close()
    assert sent
    assert sent[0] == 0
    assert 99 not in sent
    assert playback.has_chunks is True


async def test_timeout_plays_cached_cannot_speak(harness: Harness) -> None:
    sent: list[bytes] = []

    async def send(data: bytes) -> None:
        sent.append(data)

    phrase = "I am having trouble speaking. Please hold."
    cache = TtsCache(warmup_ids=frozenset({"cannot_speak"}), warmup_texts=frozenset({phrase}))
    cache.store(
        phrase,
        harness.settings.tts_voice,
        harness.settings.tts_speed,
        b"\x00" * harness.settings.tts_pcm_bytes,
        warmup=True,
    )
    pool = TtsPool.stub(
        timeout_ms=50,
        frame_bytes=harness.settings.tts_pcm_bytes,
        sleep_s=1.0,
    )
    handler = AudioOutHandler(
        session=harness.session,
        settings=harness.settings,
        metrics=harness.metrics,
        pool=pool,
        cache=cache,
        playback=PlaybackCursor(),
        send=send,
    )
    event = harness.session.create_event(
        EventKind.TTS_CHUNK,
        {"text": "long content", "voice": "default", "speed": 1.0, "filler": 0, "first_chunk": 1},
    )
    await handler(event)
    pool.close()
    assert sent
    assert sent[0][0] == MsgType.PCM
