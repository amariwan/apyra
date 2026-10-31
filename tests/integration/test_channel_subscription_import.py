"""Runtime import coverage for the public channel subscription contract."""


def test_channel_subscription_protocol_imports() -> None:
    from apyra.channels.layer import ChannelSubscription

    assert all(
        callable(getattr(ChannelSubscription, method))
        for method in ("__aiter__", "__anext__", "close")
    )
