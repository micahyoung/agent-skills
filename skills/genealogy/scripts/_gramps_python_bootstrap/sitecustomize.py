"""Bootstrap: monkey-patch macOS locale before Gramps loads."""
import locale

# Gramps calls GNU gettext locale functions that don't exist on macOS.
if not hasattr(locale, "textdomain"):
    locale.textdomain = lambda *args, **kwargs: None
if not hasattr(locale, "bindtextdomain"):
    locale.bindtextdomain = lambda *args, **kwargs: None
