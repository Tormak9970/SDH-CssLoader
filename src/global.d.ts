// Global types for the plugin

type ScheduledChange = {
  id: string,
  profileId: string,
  hours: number,
  minutes: number
}

type TimeUpdatesDict = {
  [id: string]: (event: Event) => void
}