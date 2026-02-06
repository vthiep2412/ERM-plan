import av
print("Encoders:")
try:
    for name in sorted(av.codecs_available):
        codec = av.Codec(name, 'w')
        if 'h264' in name or 'nvenc' in name:
            print(f" - {name}: {codec.long_name}")
except Exception as e:
    print(f"Error listing codecs: {e}")

try:
    c = av.Codec('h264_nvenc', 'w')
    print("\nSUCCESS: h264_nvenc is available!")
except Exception as e:
    print(f"\nFAIL: h264_nvenc not available: {e}")
# This line was added at the bottom to force re-check. 
