import av
print("Encoders:")
for name in sorted(av.codecs_available):
    try:
        # Filter first to avoid unnecessary instantiation
        if 'h264' in name or 'nvenc' in name:
            codec = av.Codec(name, 'w')
            print(f" - {name}: {codec.long_name}")
    except Exception as e:
        print(f"Error checking {name}: {e}")

try:
    c = av.Codec('h264_nvenc', 'w')
    print("\nSUCCESS: h264_nvenc is available!")
except Exception as e:
    print(f"\nFAIL: h264_nvenc not available: {e}")
# alr 
