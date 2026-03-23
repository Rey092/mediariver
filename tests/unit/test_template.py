"""Tests for Jinja2 template resolution."""


from mediariver.engine.template import evaluate_condition, resolve_dict, resolve_string


class TestResolveString:
    def test_simple_variable(self):
        ctx = {"file": {"name": "video.mp4"}}
        assert resolve_string("{{file.name}}", ctx) == "video.mp4"

    def test_nested_variable(self):
        ctx = {"steps": {"probe": {"output": "/tmp/out.json"}}}
        assert resolve_string("{{steps.probe.output}}", ctx) == "/tmp/out.json"

    def test_no_template(self):
        assert resolve_string("plain string", {}) == "plain string"

    def test_mixed_template(self):
        ctx = {"file": {"stem": "video"}}
        assert resolve_string("output/{{file.stem}}/master.m3u8", ctx) == "output/video/master.m3u8"

    def test_expression(self):
        ctx = {"steps": {"upscale": {"status": "done", "output": "/tmp/up.mp4"}}}
        result = resolve_string(
            "{{steps.upscale.output if steps.upscale.status == 'done' else 'fallback'}}",
            ctx,
        )
        assert result == "/tmp/up.mp4"

    def test_or_fallback(self):
        ctx = {"steps": {"upscale": {"output": ""}, "crop": {"output": "/tmp/crop.mp4"}}}
        result = resolve_string("{{steps.upscale.output or steps.crop.output}}", ctx)
        assert result == "/tmp/crop.mp4"

    def test_env_variable(self):
        ctx = {"env": {"S3_BUCKET": "my-bucket"}}
        assert resolve_string("{{env.S3_BUCKET}}", ctx) == "my-bucket"

    def test_undefined_variable_returns_empty(self):
        result = resolve_string("{{nonexistent.var}}", {})
        assert result == ""


class TestResolveDict:
    def test_resolve_nested_dict(self):
        ctx = {"file": {"stem": "video"}, "env": {"URL": "http://api.local"}}
        params = {
            "url": "{{env.URL}}/notify",
            "body": {
                "name": "{{file.stem}}",
                "nested": {"deep": "{{file.stem}}-hls"},
            },
        }
        result = resolve_dict(params, ctx)
        assert result["url"] == "http://api.local/notify"
        assert result["body"]["name"] == "video"
        assert result["body"]["nested"]["deep"] == "video-hls"

    def test_non_string_values_unchanged(self):
        result = resolve_dict({"count": 5, "flag": True, "items": [1, 2]}, {})
        assert result["count"] == 5
        assert result["flag"] is True
        assert result["items"] == [1, 2]

    def test_list_of_dicts_resolved(self):
        ctx = {"val": "resolved"}
        params = {"items": [{"key": "{{val}}"}]}
        result = resolve_dict(params, ctx)
        assert result["items"][0]["key"] == "resolved"


class TestEvaluateCondition:
    def test_truthy_expression(self):
        ctx = {"steps": {"probe": {"width": 1920}}}
        assert evaluate_condition("{{steps.probe.width > 0}}", ctx) is True

    def test_falsy_expression(self):
        ctx = {"steps": {"probe": {"width": 800}}}
        assert evaluate_condition("{{steps.probe.width > 1200}}", ctx) is False

    def test_string_false(self):
        assert evaluate_condition("{{false}}", {}) is False

    def test_empty_string(self):
        assert evaluate_condition("{{'' }}", {}) is False

    def test_none_condition_is_truthy(self):
        assert evaluate_condition(None, {}) is True
