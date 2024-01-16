from setuptools import Extension

#---------------------------------------------------------------------------------------------------
ext_modules = [
    Extension(name='regio.regmap.io.mmap_ext',
              sources=['src/regio/regmap/io/mmap_ext.c'],
              extra_compile_args=['-Wall', '-Werror', '-Wextra', '-Wno-conversion']),
]

#---------------------------------------------------------------------------------------------------
def build(setup_kwargs):
    setup_kwargs.update({
        'ext_modules': ext_modules,
    })
