import React, { useContext } from 'react';
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SettingsContext } from '../../contexts/SettingsContext';

export default function TabLayout() {
  const { isDarkMode, t } = useContext(SettingsContext);

  return (
    <Tabs screenOptions={{ 
      headerShown: false, 
      tabBarActiveTintColor: isDarkMode ? '#4CAF50' : '#2e7d32',
      tabBarInactiveTintColor: isDarkMode ? '#888' : '#666',
      tabBarStyle: {
        backgroundColor: isDarkMode ? '#1E1E1E' : '#FFF',
        borderTopColor: isDarkMode ? '#333' : '#E0E0E0',
      }
    }}>
      <Tabs.Screen 
        name="dashboard" 
        options={{ 
          title: t('Dashboard'),
          tabBarIcon: ({ color }) => <Ionicons name="home" size={24} color={color} />
        }} 
      />
      <Tabs.Screen 
        name="listings" 
        options={{ 
          title: t('Listings'),
          tabBarIcon: ({ color }) => <Ionicons name="list" size={24} color={color} />
        }} 
      />
      <Tabs.Screen 
        name="profile" 
        options={{ 
          title: t('Profile'),
          tabBarIcon: ({ color }) => <Ionicons name="person" size={24} color={color} />
        }} 
      />
    </Tabs>
  );
}