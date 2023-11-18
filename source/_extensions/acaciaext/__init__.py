import os
from typing import TYPE_CHECKING, Tuple, List
from sphinx.locale import get_translation
from sphinx.util.docutils import ReferenceRole
from docutils import nodes

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from docutils.nodes import Node, system_message

I18N_CATALOG = 'acaciaext'
_ = get_translation(I18N_CATALOG)

class MCWikiRole(ReferenceRole):
    def run(self) -> Tuple[List["Node"], List["system_message"]]:
        refuri = "https://%s.minecraft.wiki/w/%s" % (_("www"), self.target)
        reference = nodes.reference('', '', internal=False, refuri=refuri)
        if self.has_explicit_title:
            reference += nodes.strong(self.title, self.title)
        else:
            title = _("MCWiki: %s") % self.title
            reference += nodes.strong(title, title)
        print(refuri)
        return [reference], []

def setup(app: "Sphinx"):
    app.add_role("mcwiki", MCWikiRole())
    package_dir = os.path.abspath(os.path.dirname(__file__))
    locale_dir = os.path.join(package_dir, 'locales')
    app.add_message_catalog(I18N_CATALOG, locale_dir)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
