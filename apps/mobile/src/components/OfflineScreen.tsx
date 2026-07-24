import { Image, Pressable, Text, View } from 'react-native';

export function OfflineScreen({ onRetry }: { onRetry: () => void }) {
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: '#0c1324',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <Image
        source={require('../../assets/icon.png')}
        style={{ width: 64, height: 64, borderRadius: 16, marginBottom: 20 }}
      />
      <Text style={{ color: '#dce1fb', fontSize: 22, fontWeight: '800', marginBottom: 8 }}>
        You&apos;re offline
      </Text>
      <Text
        style={{
          color: '#c7c4d7',
          fontSize: 14,
          lineHeight: 22,
          textAlign: 'center',
          marginBottom: 24,
        }}
      >
        StudyBuddy needs a connection to load. Check your network and try again.
      </Text>
      <Pressable
        onPress={onRetry}
        style={{ backgroundColor: '#8083ff', paddingVertical: 12, paddingHorizontal: 28, borderRadius: 14 }}
      >
        <Text style={{ color: '#0c1324', fontWeight: '800', fontSize: 14 }}>Retry</Text>
      </Pressable>
    </View>
  );
}
