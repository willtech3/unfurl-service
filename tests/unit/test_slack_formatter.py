from src.unfurl_processor.slack_formatter import SlackFormatter


def test_format_unfurl_escapes_slack_mrkdwn_sequences() -> None:
    formatter = SlackFormatter()
    unfurl = formatter.format_unfurl_data(
        {
            "username": "bad<!channel>",
            "caption": "<!here> <https://evil.example|trusted> & #tag @user",
            "image_url": "https://scontent.cdninstagram.com/image.jpg",
            "url": "https://www.instagram.com/p/ABC123/",
            "content_type": "photo",
        }
    )

    assert unfurl is not None

    header_text = unfurl["blocks"][1]["text"]["text"]
    caption_text = unfurl["blocks"][2]["text"]["text"]

    assert "<!channel>" not in header_text
    assert "&lt;!channel&gt;" in header_text
    assert "<!here>" not in caption_text
    assert "<https://evil.example|trusted>" not in caption_text
    assert "&lt;!here&gt;" in caption_text
    assert "&lt;https://evil.example|trusted&gt;" in caption_text
    assert "&amp;" in caption_text


def test_video_host_validation_rejects_untrusted_fcdn_domains() -> None:
    formatter = SlackFormatter()

    assert formatter._is_instagram_video_url("https://video.xx.fbcdn.net/video.mp4")
    assert not formatter._is_instagram_video_url("https://attacker.fcdn.us/video.mp4")
