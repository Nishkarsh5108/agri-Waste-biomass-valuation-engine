import React, { useState } from 'react';
import { View, TextInput, StyleSheet, Text, ActivityIndicator, Alert, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE_URL } from '../constants';

export default function LoginScreen() {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();

  const handleLogin = async () => {
    if (!phone || !password) {
      Alert.alert("Error", "Please enter phone and password.");
      return;
    }

    setLoading(true);
    try {
      // FastAPI ka login endpoint x-www-form-urlencoded format mangta hai
      const formData = new URLSearchParams();
      formData.append('username', phone); // Backend maps 'username' to 'phone_number'
      formData.append('password', password);

      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      const data = await response.json();
      console.log("Login API Response:", data);

      if (response.ok && data.access_token) {
        // Token save karein
        await AsyncStorage.setItem('userToken', data.access_token);
        
        Alert.alert("Success", "Logged in successfully!");
        
        // Seedha dashboard par bhejein
        router.replace('/(tabs)/dashboard'); 
      } else {
        Alert.alert("Login Failed", data.detail || "Incorrect phone number or password");
      }
    } catch (err) {
      console.error("Login Error:", err);
      Alert.alert("Error", "Could not connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome Back 🌾</Text>
      
      <View style={styles.inputWrapper}>
        <TextInput 
          placeholder="Phone Number" 
          value={phone} 
          onChangeText={setPhone} 
          style={styles.input} 
          keyboardType="numeric" 
        />
      </View>

      <View style={styles.inputWrapper}>
        <TextInput 
          placeholder="Password" 
          value={password} 
          onChangeText={setPassword} 
          secureTextEntry={!showPassword} 
          style={styles.input} 
        />
        <TouchableOpacity onPress={() => setShowPassword(!showPassword)}>
          <Ionicons name={showPassword ? "eye" : "eye-off"} size={20} color="gray" />
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#2E7D32" />
      ) : (
        <TouchableOpacity style={styles.button} onPress={handleLogin}>
          <Text style={styles.btnText}>Login</Text>
        </TouchableOpacity>
      )}

      {/* Button to go back to Register if they don't have an account */}
      <TouchableOpacity onPress={() => router.replace('/')} style={styles.linkButton}>
        <Text style={styles.linkText}>Don&apos;t have an account? Register here</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 20, backgroundColor: '#F1F8E9' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#2E7D32', marginBottom: 20, textAlign: 'center' },
  inputWrapper: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', padding: 10, borderRadius: 10, marginBottom: 15, borderWidth: 1, borderColor: '#CCC' },
  input: { flex: 1, padding: 5, color: '#333' },
  button: { backgroundColor: '#2E7D32', padding: 15, borderRadius: 10, alignItems: 'center', marginTop: 10 },
  btnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  linkButton: { marginTop: 20, alignItems: 'center' },
  linkText: { color: '#2E7D32', fontSize: 14, fontWeight: '500', textDecorationLine: 'underline' }
});