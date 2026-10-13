/** Element ids shared by <Tabs> and the tab panel the page renders. */
export const tabId = (idBase: string, key: string) => `${idBase}-tab-${key}`;
export const tabPanelId = (idBase: string) => `${idBase}-panel`;
