import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, TouchableOpacity, View, Alert, Dimensions, Linking, TextInput, KeyboardAvoidingView, Platform } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, { useSharedValue, useAnimatedStyle, withRepeat, withTiming, Easing } from 'react-native-reanimated';

const { width, height } = Dimensions.get('window');
const SCAN_AREA_SIZE = 280;

export default function ScannerScreen() {
  const [facing, setFacing] = useState('back');
  const [permission, requestPermission] = useCameraPermissions();
  const [scanned, setScanned] = useState(false);
  const [torchEnabled, setTorchEnabled] = useState(false);
  const [mobileMode, setMobileMode] = useState(false);
  const [mobileNumber, setMobileNumber] = useState('');
  const router = useRouter();

  const scanLineY = useSharedValue(0);

  useEffect(() => {
    // Start scanning line animation
    scanLineY.value = withRepeat(
      withTiming(SCAN_AREA_SIZE, {
        duration: 2000,
        easing: Easing.inOut(Easing.ease),
      }),
      -1,
      true
    );
  }, []);

  const animatedStyle = useAnimatedStyle(() => {
    return {
      transform: [{ translateY: scanLineY.value }],
    };
  });

  if (!permission) {
    return <View style={styles.container} />;
  }

  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.iconButton}>
            <Ionicons name="close" size={28} color="#FFF" />
          </TouchableOpacity>
        </View>
        <View style={styles.permissionContainer}>
          <View style={styles.permissionIconCircle}>
            <Ionicons name="camera" size={48} color="#2E7D32" />
          </View>
          <Text style={styles.permissionTitle}>Camera Access Required</Text>
          <Text style={styles.permissionMessage}>We need your permission to access the camera in order to scan QR codes.</Text>
          <TouchableOpacity style={styles.permissionButton} onPress={requestPermission}>
            <Text style={styles.permissionButtonText}>Enable Camera</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  const handleBarcodeScanned = ({ type, data }: { type?: string; data: string }) => {
    if (scanned) return;
    setScanned(true);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    
    let upiId = data;
    // Extract UPI ID if it's a full URI, else assume it's just the ID
    if (data.includes('upi://pay?pa=')) {
      const match = data.match(/pa=([^&]+)/);
      if (match) upiId = match[1];
    } else if (/^\d{10}$/.test(data)) {
      // If it's a raw 10 digit number from manual input
      upiId = `${data}@upi`;
    }

    Alert.alert(
      "UPI Payment",
      `Send payment to: ${upiId}\nChoose your payment app:`,
      [
        { text: "GPay", onPress: () => { Linking.openURL(`upi://pay?pa=${upiId}&pn=Farmer`); setScanned(false); setMobileMode(false); } },
        { text: "PhonePe", onPress: () => { Linking.openURL(`phonepe://pay?pa=${upiId}&pn=Farmer`); setScanned(false); setMobileMode(false); } },
        { text: "Cancel", onPress: () => { setScanned(false); setMobileMode(false); }, style: 'cancel' }
      ]
    );
  };

  const handleMobileSubmit = () => {
    if (!/^\d{10}$/.test(mobileNumber)) {
      Alert.alert("Invalid Number", "Please enter a valid 10-digit mobile number.");
      return;
    }
    handleBarcodeScanned({ data: mobileNumber });
  };

  const toggleTorch = () => {
    setTorchEnabled(prev => !prev);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  const toggleCamera = () => {
    setFacing(prev => (prev === 'back' ? 'front' : 'back'));
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  };

  return (
    <View style={styles.container}>
      <CameraView 
        style={StyleSheet.absoluteFillObject} 
        facing={facing as any}
        enableTorch={torchEnabled}
        onBarcodeScanned={scanned ? undefined : handleBarcodeScanned}
        barcodeScannerSettings={{
          barcodeTypes: ["qr"],
        }}
      >
        <View style={styles.overlay}>
          {/* Top Overlay */}
          <View style={styles.overlayMask} />
          
          <View style={styles.middleSection}>
            <View style={styles.overlayMask} />
            <View style={styles.scanArea}>
              {/* Corner Brackets */}
              <View style={[styles.corner, styles.topLeft]} />
              <View style={[styles.corner, styles.topRight]} />
              <View style={[styles.corner, styles.bottomLeft]} />
              <View style={[styles.corner, styles.bottomRight]} />
              
              {/* Animated Scan Line */}
              {!scanned && (
                <Animated.View style={[styles.scanLine, animatedStyle]} />
              )}
            </View>
            <View style={styles.overlayMask} />
          </View>

          {/* Bottom Overlay */}
          <View style={[styles.overlayMask, styles.bottomOverlay]}>
            <Text style={styles.instructionText}>
              Align QR code within the frame to scan
            </Text>
          </View>
        </View>
      </CameraView>

      {/* Header Controls Overlay */}
      <View style={styles.headerControls}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconButton}>
          <Ionicons name="close" size={32} color="#FFF" />
        </TouchableOpacity>
      </View>

      {/* Bottom Controls Overlay */}
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'} 
        style={styles.bottomControlsContainer}
      >
        {mobileMode ? (
          <View style={styles.mobileInputContainer}>
            <TextInput
              style={styles.mobileInput}
              placeholder="Enter 10-digit Mobile No."
              placeholderTextColor="#999"
              keyboardType="phone-pad"
              maxLength={10}
              value={mobileNumber}
              onChangeText={setMobileNumber}
              autoFocus
            />
            <View style={styles.mobileBtnRow}>
              <TouchableOpacity style={styles.cancelMobileBtn} onPress={() => { setMobileMode(false); setMobileNumber(''); }}>
                <Text style={styles.controlText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.submitMobileBtn} onPress={handleMobileSubmit}>
                <Text style={styles.controlText}>Pay</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.bottomControls}>
            <TouchableOpacity style={styles.controlBtn} onPress={() => setMobileMode(true)}>
              <Ionicons name="call" size={28} color="#FFF" />
              <Text style={styles.controlText}>Pay via No.</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.controlBtn} onPress={toggleTorch}>
              <Ionicons name={torchEnabled ? "flash" : "flash-off"} size={28} color={torchEnabled ? "#FFD700" : "#FFF"} />
              <Text style={styles.controlText}>Flash</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.controlBtn} onPress={toggleCamera}>
              <Ionicons name="camera-reverse" size={28} color="#FFF" />
              <Text style={styles.controlText}>Flip</Text>
            </TouchableOpacity>
          </View>
        )}
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  header: {
    flexDirection: 'row', 
    alignItems: 'center', 
    padding: 20, 
    paddingTop: 50,
  },
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 30,
    backgroundColor: '#121212'
  },
  permissionIconCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: 'rgba(46, 125, 50, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  permissionTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
  },
  permissionMessage: {
    textAlign: 'center',
    fontSize: 16,
    color: '#A0A0A0',
    marginBottom: 32,
    lineHeight: 24,
  },
  permissionButton: {
    backgroundColor: '#2E7D32',
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 30,
    width: '100%',
    alignItems: 'center',
    shadowColor: '#2E7D32',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  permissionButtonText: {
    color: '#FFF',
    fontWeight: '700',
    fontSize: 16,
  },
  overlay: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  overlayMask: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
  },
  middleSection: {
    flexDirection: 'row',
    height: SCAN_AREA_SIZE,
  },
  scanArea: {
    width: SCAN_AREA_SIZE,
    height: SCAN_AREA_SIZE,
    backgroundColor: 'transparent',
    overflow: 'hidden',
  },
  bottomOverlay: {
    justifyContent: 'flex-start',
    alignItems: 'center',
    paddingTop: 40,
  },
  instructionText: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 16,
    fontWeight: '500',
    letterSpacing: 0.5,
  },
  corner: {
    position: 'absolute',
    width: 40,
    height: 40,
    borderColor: '#4CAF50',
  },
  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
    borderTopLeftRadius: 16,
  },
  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
    borderTopRightRadius: 16,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderBottomLeftRadius: 16,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderBottomRightRadius: 16,
  },
  scanLine: {
    width: '100%',
    height: 2,
    backgroundColor: '#4CAF50',
    shadowColor: '#4CAF50',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 10,
    elevation: 5,
  },
  headerControls: {
    position: 'absolute',
    top: 50,
    left: 20,
    right: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    zIndex: 2,
  },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  bottomControls: {
    position: 'absolute',
    bottom: 40,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    alignItems: 'center',
    zIndex: 2,
  },
  controlBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 16,
  },
  controlText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 6,
  },
  bottomControlsContainer: {
    position: 'absolute',
    bottom: 40,
    left: 0,
    right: 0,
    zIndex: 2,
  },
  mobileInputContainer: {
    backgroundColor: 'rgba(0,0,0,0.85)',
    marginHorizontal: 20,
    padding: 20,
    borderRadius: 16,
    alignItems: 'center',
  },
  mobileInput: {
    backgroundColor: '#FFF',
    width: '100%',
    padding: 15,
    borderRadius: 8,
    fontSize: 18,
    textAlign: 'center',
    marginBottom: 15,
  },
  mobileBtnRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
  },
  cancelMobileBtn: {
    flex: 1,
    backgroundColor: '#D32F2F',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginRight: 10,
  },
  submitMobileBtn: {
    flex: 1,
    backgroundColor: '#2E7D32',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginLeft: 10,
  }
});
