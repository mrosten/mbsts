import jinja2
import yaml
from box import Box
import os


class SproutConfiguration():
    def __init__(self, path='./', file='config.yaml.j2'):
        templateLoader = jinja2.FileSystemLoader(searchpath=path)
        templateEnv = jinja2.Environment(loader=templateLoader)
        template = templateEnv.get_template(file)
        config_yaml_str = template.render(ENV=os.environ)
        data = yaml.safe_load(config_yaml_str)
        self.config = Box(data)

    def __getattr__(self, item):
        return getattr(self.config, item)



