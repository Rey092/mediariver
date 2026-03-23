"""Action imports — triggers @register_action decorators."""

# Audio actions
import mediariver.actions.audio.convert  # noqa: F401
import mediariver.actions.audio.duration_check  # noqa: F401
import mediariver.actions.audio.embed_art  # noqa: F401
import mediariver.actions.audio.hls  # noqa: F401
import mediariver.actions.audio.info  # noqa: F401
import mediariver.actions.audio.normalize  # noqa: F401
import mediariver.actions.audio.tag  # noqa: F401

# isort: split
# Filesystem actions
import mediariver.actions.copy  # noqa: F401
import mediariver.actions.delete  # noqa: F401
import mediariver.actions.move  # noqa: F401
import mediariver.actions.util.docker_run  # noqa: F401
import mediariver.actions.util.http  # noqa: F401

# isort: split
# Image actions
import mediariver.actions.image.convert  # noqa: F401
import mediariver.actions.image.crop  # noqa: F401
import mediariver.actions.image.flip_rotate  # noqa: F401
import mediariver.actions.image.info  # noqa: F401
import mediariver.actions.image.optimize  # noqa: F401
import mediariver.actions.image.orientation_check  # noqa: F401
import mediariver.actions.image.pixel_check  # noqa: F401
import mediariver.actions.image.resize  # noqa: F401
import mediariver.actions.image.upscale  # noqa: F401

# isort: split
# Utility actions
import mediariver.actions.util.shell  # noqa: F401

# isort: split
# Video actions
import mediariver.actions.video.crop  # noqa: F401
import mediariver.actions.video.hls  # noqa: F401
import mediariver.actions.video.info  # noqa: F401
import mediariver.actions.video.normalize_audio  # noqa: F401
import mediariver.actions.video.thumbnail  # noqa: F401
import mediariver.actions.video.transcode  # noqa: F401
