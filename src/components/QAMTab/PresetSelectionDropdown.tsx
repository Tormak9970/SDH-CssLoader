import { DropdownItem, PanelSectionRow, showModal } from "decky-frontend-lib";
import { useCssLoaderState } from "../../state";
import { Flags } from "../../ThemeTypes";
import { useMemo } from "react";
import { changePreset, getInstalledThemes } from "../../python";
import { CreatePresetModalRoot } from "../AllThemes/CreatePresetModal";
import { FiPlusCircle } from "react-icons/fi";
import { useRerender } from "../../hooks";

export function PresetSelectionDropdown() {
  const { localThemeList, selectedPreset } = useCssLoaderState();
  const presets = useMemo(
    () => localThemeList.filter((e) => e.flags.includes(Flags.isPreset)),
    [localThemeList]
  );
  const [render, rerender] = useRerender();
  return (
    <>
      {render && (
        <PanelSectionRow>
          <DropdownItem
            label="Selected Profile"
            selectedOption={
              localThemeList.filter((e) => e.enabled && e.flags.includes(Flags.isPreset)).length > 1
                ? "Invalid State"
                : selectedPreset?.name || "None"
            }
            rgOptions={[
              ...(localThemeList.filter((e) => e.enabled && e.flags.includes(Flags.isPreset))
                .length > 1
                ? [{ data: "Invalid State", label: "Invalid State" }]
                : []),
              { data: "None", label: "None" },
              ...presets.map((e) => ({ label: e.name, data: e.name })),
              // This is a jank way of only adding it if creatingNewProfile = false
              {
                data: "New Profile",
                label: (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "start",
                      gap: "1em",
                    }}
                  >
                    <FiPlusCircle />
                    <span>New Profile</span>
                  </div>
                ),
              },
            ]}
            onChange={async ({ data }) => {
              if (data === "New Profile") {
                showModal(
                  // @ts-ignore
                  <CreatePresetModalRoot />
                );
                rerender();
                return;
              }
              // This is kind of abusing the system because if you select "None" it attempts to enable a theme called "None"
              // But it works
              await changePreset(data, localThemeList);
              getInstalledThemes();
            }}
          />
        </PanelSectionRow>
      )}
    </>
  );
}
