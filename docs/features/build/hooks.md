# Build — Hooks

The build domain exposes **no hook actions** for tool packages today.

The build's extension surface is configuration-shaped instead: custom ralph-loop prompts (`build.prompts_dir`), custom agent definitions (`build.agents_dir`), and any CLI agent whose wrapper exists in the image (see [Configuration](configuration.md)). The platform mechanism behind every hook action is covered in [Hooks](../hooks/index.md).
