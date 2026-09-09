import { createContext, useContext } from "react";

interface UIContextValue {
  sidebarCollapsed: boolean;
  toggleSidebarCollapsed: () => void;
  mobileNavOpen: boolean;
  setMobileNavOpen: (open: boolean) => void;
}

export const UIContext = createContext<UIContextValue>({
  sidebarCollapsed: false,
  toggleSidebarCollapsed: () => {},
  mobileNavOpen: false,
  setMobileNavOpen: () => {},
});

export function useUI(): UIContextValue {
  return useContext(UIContext);
}
