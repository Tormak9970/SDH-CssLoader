import { VFC, useEffect, useMemo, useState } from "react";
import { Flags, Theme } from "../../ThemeTypes";
import { useCssLoaderState } from "../../state";
import { changePreset, setProfileSchedule } from "../../python";
import { DialogButton, Dropdown, Focusable, ReorderableEntry, ReorderableList } from "decky-frontend-lib";
import { FaRegClock } from "react-icons/fa";

export function generateListenerForSchedule(scheduledChange: ScheduledChange, existsCheck: (profile: string) => boolean, setProfile: (profile: string) => void, removeScheduledChange: (change: ScheduledChange) => Promise<void>): () => void {
  return () => {
    const today = new Date();
    
    if (today.getHours() === scheduledChange.hours && today.getMinutes() === scheduledChange.minutes) {
      if (existsCheck(scheduledChange.profileId)) {
        setProfile(scheduledChange.profileId);
      } else {
        removeScheduledChange(scheduledChange);
      }
    }
  }
}

type InteractableButtonProps<T> = {
  entry: ReorderableEntry<T>
}

function PresetDropdown(props: { change: ScheduledChange }) {
  const { localThemeList, selectedPreset } = useCssLoaderState();
  const presets = useMemo(
    () => localThemeList.filter((e) => e.flags.includes(Flags.isPreset)),
    [localThemeList]
  );

  return (
    <Dropdown
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
        ...presets.map((e) => ({ label: e.display_name, data: e.name })),
        // This is a jank way of only adding it if creatingNewProfile = false
      ]}
      onChange={({ data }) => {
        // TODO: change this scheduled change's entry to be the new profile
      }}
    />
  );
}

function ChangeTimeButton(props: { change: ScheduledChange }){
  function onAction(): void {
    // TODO: here we can show a modal allowing the user to change the time
  }

  return (
    <DialogButton
      style={{
        height: "40px",
        minWidth: "40px",
        width: "40px",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "10px"
      }}
      onClick={onAction}
      onOKButton={onAction}
    >
      <FaRegClock />
    </DialogButton>
  );
}


type ProfileScheduleProps = {

}

export const ProfileSchedule: VFC<ProfileScheduleProps> = (props: ProfileScheduleProps) => {
  const { schedule, timeUpdates, localThemeList, getGlobalState, setGlobalState } = useCssLoaderState();
  const [ presets, setPresets ] = useState<Theme[]>(localThemeList.filter((localTheme: Theme) => localTheme.flags.includes(Flags.isPreset)));
  const [ scheduleList, setScheduleList ] = useState();

  useEffect(() => {
    setPresets(localThemeList.filter((localTheme: Theme) => localTheme.flags.includes(Flags.isPreset)));
  }, [localThemeList]);


  async function removeScheduledChange(scheduledChange: ScheduledChange): Promise<void> {
    const tmpSchedule = [...schedule];
    const tmpUpdates = {...timeUpdates};

    const oldListener = tmpUpdates[scheduledChange.id];
    window.removeEventListener("timeupdate", oldListener);

    delete tmpUpdates[scheduledChange.id];

    let tmpScheduleEntryIdx = tmpSchedule.findIndex((tmp: ScheduledChange) => tmp.id === scheduledChange.id);
    tmpSchedule.splice(tmpScheduleEntryIdx, 1);
    
    setGlobalState("schedule", tmpSchedule);
    setGlobalState("timeUpdates", tmpUpdates);
    await setProfileSchedule(schedule);
  }

  async function setScheduledChange(scheduledChange: ScheduledChange): Promise<void> {
    const tmpSchedule = [...schedule];
    const tmpUpdates = {...timeUpdates};

    const checkExists = (profileId: string) => (getGlobalState("localThemeList") as Theme[]).filter((localTheme: Theme) => localTheme.flags.includes(Flags.isPreset)).map((profile: Theme) => profile.id).includes(profileId);
    const setProfile = (profileId: string) => {
      const themeList = getGlobalState("localThemeList") as Theme[];
      const profile = themeList.filter((localTheme: Theme) => localTheme.flags.includes(Flags.isPreset)).find((theme: Theme) => theme.id === profileId);

      changePreset(profile!.name, themeList);
    }
    const listener = generateListenerForSchedule(scheduledChange, checkExists, setProfile, removeScheduledChange);

    if (!Object.keys(timeUpdates).includes(scheduledChange.id)) {
      tmpUpdates[scheduledChange.id] = listener;

      tmpSchedule.push(scheduledChange);

      window.addEventListener("timeupdate", listener);
    } else {
      const oldListener = tmpUpdates[scheduledChange.id];
      window.removeEventListener("timeupdate", oldListener);

      tmpUpdates[scheduledChange.id] = listener;

      let tmpScheduleEntryIdx = tmpSchedule.findIndex((tmp: ScheduledChange) => tmp.id === scheduledChange.id);
      tmpSchedule[tmpScheduleEntryIdx] = scheduledChange;

      window.addEventListener("timeupdate", listener);
    }

    tmpSchedule.sort((a, b) => {
      const hours = a.hours - b.hours;
      const minutes = a.minutes - b.minutes;

      if (hours !== 0) {
        return hours;
      } else {
        return minutes;
      }
    });
    
    setGlobalState("schedule", tmpSchedule);
    setGlobalState("timeUpdates", tmpUpdates);
    await setProfileSchedule(schedule);
  }

  // TODO: show message if no scheduledChanges already exist.

  return (
    <div>
      <Focusable>
        {(presets.length > 0 ? (
          <Focusable className="CSSLoader_InstalledThemes_Container">
            <Focusable className="CSSLoader_InstalledThemes_ButtonsContainer">
              <DialogButton
                className="CSSLoader_InstalledThemes_ModeButton"
                onClick={() => {}}
              >
                Add Change
              </DialogButton>
            </Focusable>
            {(schedule.length > 0 ? (
              schedule.map((scheduledChange) => (
                <div>
                  {/* TODO: this should have the a label, dropdown, and change time button. */}
                  <PresetDropdown change={scheduledChange} />
                  <ChangeTimeButton change={scheduledChange} />
                </div>
              ))
            ) : (
              <div>
                Looks like there aren't any sheduled changes yet! Click the button above to start adding them.
              </div>
            ))}
          </Focusable>
        ) : (
          <div>
            Want to schedule themes to change throughout the day? Create a few profiles in the Profiles Tab, then set up the schedules here!
          </div>
        ))}
      </Focusable>
    </div>
  );
}