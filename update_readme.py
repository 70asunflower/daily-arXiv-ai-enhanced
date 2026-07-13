import os
from os.path import join

if __name__ == '__main__':
    # ---------------------------------------------------------------------------
    # DISABLED: README.md is now maintained directly.
    # template.md does NOT contain the hand-written sections that live in
    # README.md (Key Features / Contributors / Acknowledgement / Star history),
    # so regenerating README.md from template.md would DROP that content.
    # Kept for reference only. If you really want to regenerate, reconstruct
    # template.md to mirror README.md first, then remove this guard.
    # ---------------------------------------------------------------------------
    print(
        "[update_readme.py] DISABLED: README.md is maintained directly.\n"
        "  Running this would overwrite README.md from template.md and lose "
        "hand-written sections.\n"
        "  Aborting to prevent data loss."
    )
    raise SystemExit(0)

    template = open('template.md', 'r').read()
    data = sorted(os.listdir('data'), reverse=True)

    readme_content_template = open('readme_content_template.md', 'r').read()
    readme_content = "\n\n".join(
        [readme_content_template.format(date=item.replace('.md', ''),url=join('data', item)) for item in data if item.endswith('.md')]
    )
    markdown = template.format(readme_content=readme_content)
    with open('README.md', 'w') as f:
        f.write(markdown)
