pub fn roman_to_int_impl(roman: &str) -> Result<i32, String> {
    fn value_of(ch: char) -> Option<i32> {
        match ch {
            'I' => Some(1),
            'V' => Some(5),
            'X' => Some(10),
            'L' => Some(50),
            'C' => Some(100),
            'D' => Some(500),
            'M' => Some(1000),
            _ => None,
        }
    }

    let mut total = 0;
    let mut prev = 0;

    for ch in roman.chars().rev() {
        let value = value_of(ch).ok_or_else(|| ch.to_string())?;
        if value < prev {
            total -= value;
        } else {
            total += value;
            prev = value;
        }
    }

    Ok(total)
}
