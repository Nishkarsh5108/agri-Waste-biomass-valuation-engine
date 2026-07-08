import React, { useEffect, useState } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ActivityIndicator, View } from 'react-native';
import { SettingsProvider } from '../contexts/SettingsContext';

export default function RootLayout() {
  const [isReady, setIsReady] = useState(false);
  const router = useRouter();
  const segments = useSegments();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = await AsyncStorage.getItem('userToken');
        
        // Agar token mil gaya aur hum abhi login/register screen par hain
        // toh dashboard par bhej do
        if (token && ((segments[0] as any) === 'index' || segments[0] === 'login' || !segments[0])) {
          router.replace('/(tabs)/dashboard');
        }
      } catch (error) {
        console.error("Auth check error:", error);
      } finally {
        setIsReady(true);
      }
    };

    checkAuth();
  }, [segments]);

  // Jab tak check nahi hota, ek blank screen ya spinner dikhao
  if (!isReady) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#2E7D32" />
      </View>
    );
  }

  return (
    <SettingsProvider>
      <Stack screenOptions={{ headerShown: false }}>
        {/* Root Screens */}
        <Stack.Screen name="index" /> 
        <Stack.Screen name="login" />
        <Stack.Screen name="add-farm" />
        
        {/* Tabs Folder */}
        <Stack.Screen name="(tabs)" />
      </Stack>
    </SettingsProvider>
  );
}