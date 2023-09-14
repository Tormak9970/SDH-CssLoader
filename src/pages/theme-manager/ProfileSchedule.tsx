import { VFC, useEffect, useState } from "react";
import { Flags, Theme } from "../../ThemeTypes";
import { useCssLoaderState } from "../../state";
import { changePreset, setProfileSchedule } from "../../python";

type ProfileScheduleProps = {

}

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

export const ProfileSchedule: VFC<ProfileScheduleProps> = (props: ProfileScheduleProps) => {
  const { schedule, timeUpdates, localThemeList, getGlobalState, setGlobalState } = useCssLoaderState();
  const [ presets, setPresets ] = useState<Theme[]>(localThemeList.filter((localTheme: Theme) => localTheme.flags.includes(Flags.isPreset)));

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
    <>
      {(presets.length > 0 ? (
        // {(schedule.length === 0 ? (<div>Click the button below to start adding schedules!</div>) : (<></>))}
        <div>

        </div>
      ) : (
        <div>
          Want to schedule themes to change throughout the day? Create a few profiles in the Theme Manager, then set up the schedules here!
        </div>
      ))}
    </>
  );
}