# Package reference

API pages are generated from each package's public `apyra.<package>` module and docstrings. Package
level exports are the declared stable surface; implementation submodules remain internal unless a
package explicitly documents otherwise.

Start with [`apyra.core`](core.md) and [`apyra.fastapi`](fastapi.md). Add infrastructure references
only for packages the application installs. The [`apyra` metapackage](meta.md) groups installation
extras but does not create a top-level module.

!!! note "Generated from source"

    Signatures and member descriptions below are produced by mkdocstrings. Correct inaccurate API
    text in the owning Python docstring rather than duplicating it in Markdown.
