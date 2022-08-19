import os, json, asyncio, tempfile, subprocess, shutil
from time import sleep
from os import geteuid, mkdir, path
from typing import List
from utilities import Utilities
from injector import inject_to_tab, get_tab, tab_has_element
from logging import getLogger, basicConfig, INFO, DEBUG

pluginManagerUtils = Utilities(None)
Initialized = False
CSS_LOADER_VER = 2
Logger = getLogger("CSS_LOADER")

def Log(text : str):
    Logger.info(text)

def createDir(dirPath : str):
    if (path.exists(dirPath)):
        return

    os.mkdir(dirPath)

    if (os.stat(dirPath).st_uid != 1000):
        os.chown(dirPath, 1000, 1000) # Change to deck user

class Result:
    def __init__(self, success : bool, message : str = "Success"):
        self.success = success
        self.message = message

        if not self.success:
            Log(f"Result failed! {message}")
    
    def raise_on_failure(self):
        if not self.success:
            raise Exception(self.message)

    def to_dict(self):
        return {"success": self.success, "message": self.message}

class Inject:
    def __init__(self, cssPath : str, tabs : List[str], theme):
        self.css = None
        self.cssPath = cssPath
        self.tabs = tabs
        self.uuids = {}
        self.theme = theme
        self.enabled = False
        for x in self.tabs:
            self.uuids[x] = []

    async def load(self) -> Result:
        try:
            with open(self.cssPath, "r") as fp:
                self.css = fp.read()

            Log(f"Loaded css at {self.cssPath}")
            self.css = self.css.replace("\\", "\\\\").replace("`", "\\`")

            return Result(True)
        except Exception as e:
            return Result(False, str(e))

    async def inject(self, tab : str = None) -> Result:
        if (tab is None):
            for x in self.tabs:
                await self.inject(x)

            return Result(True)
        else:
            if (tab not in self.tabs):
                return Result(True) # this is kind of cheating but

        if (len(self.uuids[tab]) > 0):
            await self.remove(tab)
            self.enabled = True # In case the below code fails, it will never be re-injected unless it's still enabled

        if (self.css is None):
            result = await self.load()
            if not result.success:
                return result        

        try:
            res = await pluginManagerUtils.inject_css_into_tab(tab, self.css)
            if not res["success"]:
                return Result(False, str(res["result"]))
            
            Log(f"+{str(res['result'])} @ {tab}")
            self.uuids[tab].append(str(res["result"]))
        except Exception as e:
            return Result(False, str(e))

        self.enabled = True
        return Result(True)

    async def remove(self, tab : str = None) -> Result:
        if (tab is None):
            for x in self.tabs:
                await self.remove(x)

            return Result(True)
        else:
            if (tab not in self.tabs):
                return Result(True) # this is kind of cheating but

        if (len(self.uuids[tab]) <= 0):
            return Result(True) # this is kind of cheating but

        try:
            for x in self.uuids[tab]:
                Log(f"-{x} @ {tab}")
                res = await pluginManagerUtils.remove_css_from_tab(tab, x)
                #if not res["success"]:
                #    return Result(False, res["result"])
                # Silently ignore error. If any page gets reloaded, and there was css loaded. this will fail as it will fail to remove the css

            self.uuids[tab] = []
        except Exception as e:
            return Result(False, str(e))

        self.enabled = False
        return Result(True)

class Theme:
    def __init__(self, themePath : str, json : dict, configPath : str = None):
        self.name = json["name"]
        self.version = json["version"] if ("version" in json) else "v1.0"
        self.author = json["author"] if ("author" in json) else ""
        self.require = int(json["manifest_version"]) if ("manifest_version" in json) else 1

        if (CSS_LOADER_VER < self.require):
            raise Exception("A newer version of the CssLoader is required to load this theme")

        self.patches = []
        self.injects = []

        self.configPath = configPath if (configPath is not None) else themePath
        self.configJsonPath = self.configPath + "/config" + ("_ROOT.json" if os.geteuid() == 0 else "_USER.json")
        self.themePath = themePath
        self.bundled = self.configPath != self.themePath
        self.dependencies = json["dependencies"] if "dependencies" in json else {}

        self.enabled = False
        self.json = json

        if "inject" in self.json:
            self.injects = [Inject(self.themePath + "/" + x, self.json["inject"][x], self) for x in self.json["inject"]]
        
        if "patches" in self.json:
            self.patches = [ThemePatch(self, self.json["patches"][x], x) for x in self.json["patches"]]
    
    async def load(self) -> Result:
        if not path.exists(self.configJsonPath):
            return Result(True)

        try:
            with open(self.configJsonPath, "r") as fp:
                config = json.load(fp)
        except Exception as e:
            return Result(False, str(e))
        
        activate = False

        for x in config:
            if x == "active" and config["active"]:
                activate = True
            else:
                for y in self.patches:
                    if y.name == x:
                        y.set_value(config[x])
        
        if activate:
            result = await self.inject()
            if not result.success:
                return result
        
        return Result(True)

    async def save(self) -> Result:
        createDir(self.configPath)

        try:
            config = {"active": self.enabled}
            for x in self.patches:
                config[x.name] = x.get_value()
            
            with open(self.configJsonPath, "w") as fp:
                json.dump(config, fp)
        
        except Exception as e:
            return Result(False, str(e))
        
        return Result(True)

    async def inject(self) -> Result:
        Log(f"Injecting theme '{self.name}'")
        for x in self.injects:
            result = await x.inject()
            if not result.success:
                return result

        for x in self.patches:
            result = await x.inject()
            if not result.success:
                return result
        
        self.enabled = True
        await self.save()
        return Result(True)
    
    async def remove(self) -> Result:
        Log(f"Removing theme '{self.name}'")
        for x in self.get_all_injects():
            result = await x.remove()
            if not result.success:
                return result

        self.enabled = False
        await self.save()
        return Result(True)

    async def delete(self) -> Result:
        if (self.bundled):
            return Result(False, "Can't delete a bundled theme")

        result = await self.remove()
        if not result.success:
            return result
        
        try:
            shutil.rmtree(self.themePath)
        except Exception as e:
            return Result(False, str(e))
        
        return Result(True)

    def get_all_injects(self) -> List[Inject]:
        injects = []
        injects.extend(self.injects)
        for x in self.patches:
            injects.extend(x.injects)
        
        return injects
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "enabled": self.enabled,
            "patches": [x.to_dict() for x in self.patches],
            "bundled": self.bundled,
            "require": self.require,
            "dependencies": [x for x in self.dependencies]
        }

class ThemePatchComponent:
    def __init__(self, themePatch, component : dict):
        self.themePatch = themePatch

        # Intentionally not doing error checking here. This should error when loaded incorrectly
        self.name = component["name"]
        self.type = component["type"]

        if self.type not in ["color-picker"]:
            raise Exception(f"Unknown component type '{self.type}'")

        self.default = component["default"]
        self.value = self.default
        self.on = component["on"]
        self.css_variable = component["css_variable"]

        self.tabs = component["tabs"]
        self.inject = Inject("", self.tabs, self.themePatch.theme)
        self.generate()

    def generate(self) -> Result:
        if (";" in self.css_variable or ";" in self.value):
            raise Exception("???")

        self.inject.css = f":root {{ --{self.css_variable}: {self.value}; }}"
        return Result(True)

    async def generate_and_reinject(self) -> Result:
        self.generate()
        if (self.inject.enabled):
            result = await self.inject.inject()
            if not result.success:
                return result
        
        return Result(True)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "on": self.on,
            "value": self.value,
        }

class ThemePatch:
    def __init__(self, theme : Theme, json : dict, name : str):
        self.json = json
        self.name = name
        self.default = json["default"]
        self.type = json["type"] if "type" in json else "dropdown"
        self.theme = theme
        self.value = self.default
        self.injects = []
        self.options = {}
        self.patchVersion = None
        self.components = []

        if "values" in json: # Do we have a v2 or a v1 format?
            self.patchVersion = 2
            for x in json["values"]:
                self.options[x] = []
        else:
            self.patchVersion = 1
            for x in json:
                if (x == "default"):
                    continue

                self.options[x] = []
        
        if self.default not in self.options:
            raise Exception(f"In patch '{self.name}', '{self.default}' does not exist as a patch option")
        
        self.load()

    def set_value(self, value):
        if isinstance(value, str):
            self.value = value
        elif isinstance(value, dict):
            if "value" in value:
                self.value = value["value"]
            
            if "components" in value:
                components = value["components"]

                if not isinstance(components, dict):
                    raise Exception("???")
                
                for x in self.components:
                    if x.name in components:
                        x.value = components[x.name]
                        x.generate()
    
    def get_value(self) -> str | dict:
        if len(self.components) <= 0:
            return self.value
        else:
            components = {}
            for x in self.components:
                components[x.name] = x.value
            
            return {
                "value": self.value,
                "components": components,
            }

    def check_value(self):
        if (self.value not in self.options):
            self.value = self.default

        if (self.type not in ["dropdown", "checkbox", "slider"]):
            self.type = "dropdown"
        
        if (self.type == "checkbox"):
            if not ("No" in self.options and "Yes" in self.options):
                self.type = "dropdown"
    
    def load(self):
        for x in self.options:
            data = self.json[x] if self.patchVersion == 1 else self.json["values"][x]

            for y in data:
                inject = Inject(self.theme.themePath + "/" + y, data[y], self.theme)
                self.injects.append(inject)
                self.options[x].append(inject)
        
        if "components" in self.json:
            for x in self.json["components"]:
                component = ThemePatchComponent(self, x)
                if component.on not in self.options:
                    raise Exception("Component references non-existent value")
                
                self.components.append(component)
                self.injects.append(component.inject)
                self.options[component.on].append(component.inject)

        self.check_value()

    async def inject(self) -> Result:
        self.check_value()
        Log(f"Injecting patch '{self.name}' of theme '{self.theme.name}'")
        for x in self.options[self.value]:
            result = await x.inject()
            if not result.success:
                return result
        
        return Result(True)

    async def remove(self) -> Result:
        self.check_value()
        Log(f"Removing patch '{self.name}' of theme '{self.theme.name}'")
        for x in self.injects:
            result = await x.remove()
            if not result.success:
                return result
        
        return Result(True)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "default": self.default,
            "value": self.value,
            "options": [x for x in self.options],
            "type": self.type,
            "components": [x.to_dict() for x in self.components]
        }

class RemoteInstall:
    def __init__(self, plugin):
        self.themeDb = "https://github.com/suchmememanyskill/CssLoader-ThemeDb/releases/download/1.1.0/themes.json"
        self.plugin = plugin
        self.themes = []

    async def run(self, command : str) -> str:
        proc = await asyncio.create_subprocess_shell(command,        
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()
        if (proc.returncode != 0):
            raise Exception(f"Process exited with error code {proc.returncode}")

        return stdout.decode()

    async def load(self, force : bool = False) -> Result:
        try:
            if force or (self.themes == []):
                response = await self.run(f"curl {self.themeDb} -L")
                self.themes = json.loads(response)
                Log(f"Got {len(self.themes)} from the themedb")
        except Exception as e:
            return Result(False, str(e))
        
        return Result(True)

    async def get_theme_db_entry_by_uuid(self, uuid : str) -> dict:
        result = await self.load()
        if not result.success:
            raise Exception(result.message)

        for x in self.themes:
            if x["id"] == uuid:
                return x
            
        raise Exception(f"No theme with id {uuid} found")

    async def get_theme_db_entry_by_name(self, name : str) -> dict:
        result = await self.load()
        if not result.success:
            raise Exception(result.message)

        for x in self.themes:
            if x["name"] == name:
                return x
            
        raise Exception(f"No theme with name {name} found")

    async def install(self, uuid : str) -> Result:
        try:
            theme = await self.get_theme_db_entry_by_uuid(uuid)
            tempDir = tempfile.TemporaryDirectory()

            Log(f"Downloading {theme['download_url']} to {tempDir.name}...")
            themeZipPath = os.path.join(tempDir.name, 'theme.zip')
            await self.run(f"curl \"{theme['download_url']}\" -L -o \"{themeZipPath}\"")

            Log(f"Unzipping {themeZipPath}")
            await self.run(f"unzip -o \"{themeZipPath}\" -d /home/deck/homebrew/themes")

            tempDir.cleanup()
        except Exception as e:
            return Result(False, str(e))

        return Result(True)

class Plugin:
    async def dummy_function(self) -> bool:
        return True

    async def get_themes(self) -> list:
        return [x.to_dict() for x in self.themes]
    
    async def set_theme_state(self, name : str, state : bool) -> dict:
        Log(f"Setting state for {name} to {state}")
        for x in self.themes:
            if (x.name == name):
                if state:
                    for y in x.dependencies:
                        dependency = await self._get_theme(self, y)
                        if dependency is not None:
                            if dependency.enabled:
                                await dependency.remove()
                            
                            for z in x.dependencies[y]:
                                value = x.dependencies[y][z]
                                for patch in dependency.patches:
                                    if patch.name == z:
                                        patch.set_value(value)
                            
                            await self.set_theme_state(self, dependency.name, True)

                result = await x.inject() if state else await x.remove()
                return result.to_dict()
        
        return Result(False, f"Did not find theme {name}").to_dict()

    async def download_theme(self, uuid : str) -> dict:
        try:
            theme_db_entry = await self.remote.get_theme_db_entry_by_uuid(uuid)
        except Exception as e:
            return Result(False, str(e)).to_dict()

        result = await self.remote.install(uuid)
        if not result.success:
            return result.to_dict()

        possibleThemeJsonPath = os.path.join("/home/deck/homebrew/themes", theme_db_entry["name"], "theme.json")
        if (os.path.exists(possibleThemeJsonPath)):
            with open(possibleThemeJsonPath, "r") as fp:
                theme = json.load(fp)
            
            parsedTheme = Theme(possibleThemeJsonPath, theme)
            for x in parsedTheme.dependencies:
                found = False
                for y in self.themes:
                    if y.name == x:
                        found = True
                        break
                
                if not found:
                    try:
                        theme_db_dependency = await self.remote.get_theme_db_entry_by_name(x)
                        result = await self.download_theme(self, theme_db_dependency["id"])
                        if not result["success"]:
                            raise Exception(result["message"])
                    except Exception as e:
                        return Result(False, str(e)).to_dict()

        return Result(True).to_dict()
    
    async def get_theme_db_data(self) -> list:
        return self.remote.themes
    
    async def reload_theme_db_data(self) -> dict:
        return (await self.remote.load(True)).to_dict()

    async def get_backend_version(self) -> int:
        return CSS_LOADER_VER
    
    async def _get_theme(self, themeName : str) -> Theme | None:
        for x in self.themes:
            if x.name == themeName:
                return x
        
        return None

    async def _get_patch_of_theme(self, themeName : str, patchName : str) -> ThemePatch:
        theme = None
        for x in self.themes:
            if (x.name == themeName):
                theme = x
                break
        
        if theme is None:
            raise Exception(f"Did not find theme '{themeName}'")
        
        themePatch = None
        for x in theme.patches:
            if (x.name == patchName):
                themePatch = x
                break
        
        if themePatch is None:
            raise Exception(f"Did not find patch '{patchName}' for theme '{themeName}'")
        
        return themePatch

    async def set_patch_of_theme(self, themeName : str, patchName : str, value : str) -> dict:
        try:
            themePatch = await self._get_patch_of_theme(self, themeName, patchName)
        except Exception as e:
            return Result(False, str(e))
        
        if (themePatch.value == value):
            return Result(True, "Already injected").to_dict()

        if (value in themePatch.options):
            themePatch.value = value
        
        if (themePatch.theme.enabled):
            await themePatch.remove()
            await themePatch.inject()
        
        await themePatch.theme.save()
        return Result(True).to_dict()
    
    async def set_component_of_theme_patch(self, themeName : str, patchName : str, componentName : str, value : str) -> dict:
        try:
            themePatch = await self._get_patch_of_theme(self, themeName, patchName)
        except Exception as e:
            return Result(False, str(e))

        component = None
        for x in themePatch.components:
            if x.name == componentName:
                component = x
                break
        
        if component == None:
            return Result(False, f"Failed to find component '{componentName}'")
        
        component.value = value
        await component.generate_and_reinject()

        await themePatch.theme.save()
        return Result(True).to_dict()
    
    async def reset(self) -> dict:
        for x in self.injects:
            await x.remove()

        await self._load(self)
        await self._load_stage_2(self)
        return Result(True).to_dict()

    async def delete_theme(self, themeName : str) -> dict:
        theme = None

        for x in self.themes:
            if x.name == themeName:
                theme = x
                break
                
        if (theme == None):
            return Result(False, f"Could not find theme {themeName}").to_dict()
        
        result = await theme.delete()
        if not result.success:
            return result.to_dict()
        
        self.themes.remove(theme)
        await self._cache_lists(self)
        return Result(True).to_dict()

    async def _inject_test_element(self, tab : str, timeout : int = 3) -> Result:
        attempt = 0
        while True:
            if await self._check_test_element(self, tab):
                return Result(True)
            else:
                try:
                    await inject_to_tab(tab, 
                    f"""
                    (function() {{
                        const elem = document.createElement('div');
                        elem.id = "test_css_loaded";
                        document.head.append(elem);
                    }})()
                    """, False)
                except:
                    pass

                attempt += 1

                if (attempt >= timeout):
                    return Result(False, f"Inject into tab '{tab}' was attempted {timeout} times, stopping")

                await asyncio.sleep(1)
            
    
    async def _check_test_element(self, tab : str) -> bool:
        try:
            return await tab_has_element(tab, "test_css_loaded")
        except:
            return False

    async def _parse_themes(self, themesDir : str, configDir : str = None):
        if (configDir is None):
            configDir = themesDir

        possibleThemeDirs = [str(x) for x in os.listdir(themesDir)]

        for x in possibleThemeDirs:
            themePath = themesDir + "/" + x
            configPath = configDir + "/" + x
            themeDataPath = themePath + "/theme.json"


            if not path.exists(themeDataPath):
                continue
        
            Log(f"Analyzing theme {x}")
            
            try:
                with open(themeDataPath, "r") as fp:
                    theme = json.load(fp)
                    
                themeData = Theme(themePath, theme, configPath)

                if (themeData.name not in [x.name for x in self.themes]):
                    self.themes.append(themeData)
                    Log(f"Adding theme {themeData.name}")

            except Exception as e:
                Log(f"Exception while parsing a theme: {e}") # Couldn't properly parse everything

    async def _cache_lists(self):
        self.injects = []
        self.tabs = []

        for x in self.themes:
            injects = x.get_all_injects()
            self.injects.extend(injects)
            for y in injects:
                for z in y.tabs:
                    if z not in self.tabs:
                        self.tabs.append(z)

    async def _check_tabs(self):
        while True:
            await asyncio.sleep(3)
            for x in self.tabs:
                try:
                    # Log(f"Checking if tab {x} is still injected...")
                    if not await self._check_test_element(self, x):
                        Log(f"Tab {x} is not injected, reloading...")
                        await self._inject_test_element(self, x)
                        for y in self.injects:
                            if y.enabled:
                                (await y.inject(x)).raise_on_failure()
                except Exception as e:
                    Log(f":( {str(e)}")
                    pass

    async def _load(self):
        Log("Loading themes...")
        self.themes = []

        themesPath = "/home/deck/homebrew/themes"
        defaultThemesPath = "/home/deck/homebrew/plugins/SDH-CssLoader/themes"

        if (not path.exists(themesPath)):
            createDir(themesPath)

        await self._parse_themes(self, themesPath)
        if (path.exists(defaultThemesPath)):
            await self._parse_themes(self, defaultThemesPath, themesPath)
    
    async def _set_theme_score(self, theme : Theme):
        if theme.name not in self.scores:
            self.scores[theme.name] = 0
        
        for x in theme.dependencies:
            dependency = await self._get_theme(self, x)
            if dependency is not None:
                await self._set_theme_score(self, dependency)
                self.scores[dependency.name] -= 1

    async def _load_stage_2(self):
        self.scores = {}
        for x in self.themes:
            await self._set_theme_score(self, x)
        
        Log(self.scores)
        self.themes.sort(key=lambda d: self.scores[d.name])

        for x in self.themes:
            Log(f"Loading theme {x.name}")
            await x.load()
        
        await self._cache_lists(self)
        self.themes.sort(key=lambda d: d.name)

    async def _main(self):
        global Initialized
        if Initialized:
            return
        
        Initialized = True

        self.themes = []
        Log("Initializing css loader...")
        self.remote = RemoteInstall(self)
        await self.remote.load()

        await self._load(self)
        await self._inject_test_element(self, "SP", 9999)
        await self._load_stage_2(self)

        Log(f"Initialized css loader. Found {len(self.themes)} themes, which inject into {len(self.tabs)} tabs ({self.tabs}). Total {len(self.injects)} injects, {len([x for x in self.injects if x.enabled])} injected")
        await self._check_tabs(self)