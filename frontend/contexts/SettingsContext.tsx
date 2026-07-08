import React, { createContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { translations } from '../locales/translations';

interface SettingsContextType {
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
  pushNotifications: boolean;
  setPushNotifications: (val: boolean) => void;
  language: string;
  setLanguage: (val: string) => void;
  t: (key: string) => string;
}

export const SettingsContext = createContext<SettingsContextType>({
  isDarkMode: false,
  setIsDarkMode: () => {},
  pushNotifications: true,
  setPushNotifications: () => {},
  language: 'English',
  setLanguage: () => {},
  t: (key: string) => key,
});

export const SettingsProvider = ({ children }: { children: ReactNode }) => {
  const [isDarkMode, setIsDarkModeState] = useState(false);
  const [pushNotifications, setPushNotificationsState] = useState(true);
  const [language, setLanguageState] = useState('English');

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const storedDarkMode = await AsyncStorage.getItem('isDarkMode');
        const storedNotifs = await AsyncStorage.getItem('pushNotifications');
        const storedLang = await AsyncStorage.getItem('language');

        if (storedDarkMode !== null) setIsDarkModeState(storedDarkMode === 'true');
        if (storedNotifs !== null) setPushNotificationsState(storedNotifs === 'true');
        if (storedLang) setLanguageState(storedLang);
      } catch (err) {
        console.error("Failed to load settings from storage:", err);
      }
    };
    loadSettings();
  }, []);

  const setIsDarkMode = async (val: boolean) => {
    setIsDarkModeState(val);
    await AsyncStorage.setItem('isDarkMode', val.toString());
  };

  const setPushNotifications = async (val: boolean) => {
    setPushNotificationsState(val);
    await AsyncStorage.setItem('pushNotifications', val.toString());
  };

  const setLanguage = async (val: string) => {
    setLanguageState(val);
    await AsyncStorage.setItem('language', val);
  };

  const t = (key: string) => {
    const langDict = translations[language] || translations['English'];
    return langDict[key] || key;
  };

  return (
    <SettingsContext.Provider value={{
      isDarkMode, setIsDarkMode,
      pushNotifications, setPushNotifications,
      language, setLanguage,
      t
    }}>
      {children}
    </SettingsContext.Provider>
  );
};
