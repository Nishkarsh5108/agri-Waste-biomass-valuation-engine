import React, { useState } from 'react';
import { View, TextInput, StyleSheet, Text, ActivityIndicator, Alert, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { API_BASE_URL } from '../constants';

export default function RegisterScreen() {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();

  const handleRegister = async () => {
    if (!phone || !password) {
      Alert.alert("Error", "Please enter phone and password.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phone, password: password, role: 'FARMER' }),
      });

      const data = await response.json();

      if (response.ok) {
        const backendToken = data.access_token || data.token;

        if (backendToken) {
          await AsyncStorage.setItem('userToken', backendToken);
          router.replace('/(tabs)/dashboard'); 
        } else {
          Alert.alert("Success", "Account created successfully! Please login to continue.");
          router.replace('/login'); 
        }
      } else {
        Alert.alert("Failed", data.detail || "Registration failed");
      }
    } catch (err) {
      console.error(err);
      Alert.alert("Error", "Could not connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome Farmer 🌾</Text>
      
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
        <TouchableOpacity style={styles.button} onPress={handleRegister}>
          <Text style={styles.btnText}>Register</Text>
        </TouchableOpacity>
      )}

      {/* Naya Login Link add kiya gaya hai */}
      <TouchableOpacity 
        onPress={() => router.push('/login')} 
        style={styles.loginLink}
      >
        <Text style={styles.loginLinkText}>Already registered? Login here</Text>
      </TouchableOpacity>

    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 20, backgroundColor: '#F1F8E9' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#2E7D32', marginBottom: 20, textAlign: 'center' },
  inputWrapper: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', padding: 10, borderRadius: 10, marginBottom: 15, borderWidth: 1, borderColor: '#CCC' },
  input: { flex: 1, padding: 5 },
  button: { backgroundColor: '#2E7D32', padding: 15, borderRadius: 10, alignItems: 'center' },
  btnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  loginLink: { marginTop: 20, alignItems: 'center' },
  loginLinkText: { color: '#2E7D32', fontSize: 15, fontWeight: '600', textDecorationLine: 'underline' }
});