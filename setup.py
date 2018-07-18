from setuptools import setup, find_packages
setup(name='pixiegateway',
      version='0.6',
      description='Server for sharing PixieDust chart and running PixieApps',
      url='https://github.com/pixiedust/pixiegateway',
      install_requires=['pixiedust', 'jupyter_kernel_gateway', 'astunparse', 'selenium'],
      author='David Taieb',
      author_email='data38777@gmail.com',
      license='Apache 2.0',
      packages=find_packages(exclude=('tests', 'tests.*')),
      include_package_data=True,
      zip_safe=False,
      entry_points={
          'console_scripts': [
              'jupyter-pixiegateway = pixiegateway:main'
          ]
      }
     )
