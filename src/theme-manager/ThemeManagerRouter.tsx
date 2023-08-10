import { Tabs } from "decky-frontend-lib";
import { Permissions } from "../apiTypes";
import { useCssLoaderState } from "../state";
import { LogInPage } from "./LogInPage";
import { StarredThemesPage } from "./StarredThemesPage";
import { SubmissionsPage } from "./SubmissionBrowserPage";
import { ThemeBrowserPage } from "./ThemeBrowserPage";
import { UninstallThemePage } from "./UninstallThemePage";
import { ProfileSchedule } from "./ProfileSchedule";

export function ThemeManagerRouter() {
  const { apiMeData, currentTab, setGlobalState } = useCssLoaderState();
  return (
    <div
      style={{
        marginTop: "40px",
        height: "calc(100% - 40px)",
        background: "#0005",
      }}
    >
      <Tabs
        activeTab={currentTab}
        onShowTab={(tabID: string) => {
          setGlobalState("currentTab", tabID);
        }}
        tabs={[
          {
            title: "All Themes",
            content: <ThemeBrowserPage />,
            id: "ThemeBrowser",
          },
          ...(!!apiMeData
            ? [
                {
                  title: "Starred Themes",
                  content: <StarredThemesPage />,
                  id: "StarredThemes",
                },
                ...(apiMeData.permissions.includes(Permissions.viewSubs)
                  ? [
                      {
                        title: "Submissions",
                        content: <SubmissionsPage />,
                        id: "SubmissionsPage",
                      },
                    ]
                  : []),
              ]
            : []),
          {
            title: "Installed Themes",
            content: <UninstallThemePage />,
            id: "InstalledThemes",
          },
          {
            title: "Schedule",
            content: <ProfileSchedule />,
            id: "ProfileSchedule"
          },
          {
            title: "Settings",
            content: <LogInPage />,
            id: "LogInPage",
          },
        ]}
      />
    </div>
  );
}
