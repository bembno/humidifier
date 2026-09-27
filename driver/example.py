import time

from humidifier import HumidifierDriver


def main():
    with HumidifierDriver() as h:
        #h.set_off()
        print(f"Device off: {h.is_off()}")

        # h.set_stage(3)
        # print("Set to stage 1 (highest)")

        # h.set_stage(2)
        # print("Set to stage 2 (medium)")

        h.set_stage_auto(1)
        print("Set to stage 1 (highest)")
        time.sleep(60*5)  # Wait for 5 minutes
        h.set_off()
        print(f"Set to OFF, device off: {h.is_off()}")


if __name__ == "__main__":
    main()