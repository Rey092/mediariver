"""Action imports — triggers @register_action decorators."""

# Audio actions
import mediariver.actions.audio.convert  # noqa: F401
import mediariver.actions.audio.info  # noqa: F401
import mediariver.actions.audio.normalize  # noqa: F401

# Filesystem actions
import mediariver.actions.copy  # noqa: F401
import mediariver.actions.delete  # noqa: F401
import mediariver.actions.move  # noqa: F401
import mediariver.actions.util.docker_run  # noqa: F401
import mediariver.actions.util.http  # noqa: F401

# Utility actions
import mediariver.actions.util.shell  # noqa: F401
import mediariver.actions.video.crop  # noqa: F401
import mediariver.actions.video.hls  # noqa: F401

# Video actions
import mediariver.actions.video.info  # noqa: F401
import mediariver.actions.video.normalize_audio  # noqa: F401
import mediariver.actions.video.thumbnail  # noqa: F401
import mediariver.actions.video.transcode  # noqa: F401
